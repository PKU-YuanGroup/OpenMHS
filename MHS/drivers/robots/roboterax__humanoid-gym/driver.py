"""OpenMHS driver for gh.roboterax/humanoid-gym: the XBot-L MJCF (a MuJoCo family driver).

The card's entry symbol ``humanoid.scripts.sim2sim:run_mujoco`` is at
``humanoid/scripts/sim2sim.py:87``.  That loop takes a TorchScript policy and a ``Sim2simCfg`` defined only under
``__main__``, imports ``humanoid.envs`` (which pulls in Isaac Gym), and exposes no reset, step or seed of its own.
This package therefore serves the MJCF the upstream sim2sim script selects by default,
``resources/robots/XBot/mjcf/XBot-L.xml``, through ``MujocoDriver``: the bridge loads the model, checks the step
control vector against the model's ``actuator_ctrlrange`` (twelve motors, -200 to 200), integrates ``ticks`` times
and derives the world state from the model and data arrays.

The model is read in place from the read-only upstream clone at the pinned commit and is never copied into this
package or imported.  The device is simulated (R0, ``world.sim``): there is no hardware backend, no physical stop
and no operator-required limit.  This package is model-authored and unreviewed: it is checked on the fake backend
only.

MuJoCo is not installed where this package was authored, and the acceptance path must also work where it is not, so
``backends['fake']`` is the package's pure Python stand-in for the ``mujoco`` module (fake.py).  It parses the same
MJCF for the model dimensions, the twelve actuators, their explicit control ranges and the 0.001 s option step, but
its integration is a placeholder; the fidelity ``gaps`` say so.  A backend name that ``backends`` does not list
(``sim``) lets the bridge import the real ``mujoco`` module and load the same file; that path was not run here.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "resources/robots/XBot/mjcf/XBot-L.xml"
SCRIPT = "humanoid/scripts/sim2sim.py"
README = "README.md"
SETUP = "setup.py"
#: The card's ``models[1]``, relative to this package directory: the read-only clone under robots/ at the pinned
#: commit.  It is the model sim2sim.py selects when --terrain is absent (SCRIPT:178-182).
MODEL_PATH = "../../../../robots/roboterax/humanoid-gym/" + MODEL


class XBotL(MujocoDriver):
    device_id = "xbot-l"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "RobotEra XBot-L humanoid (MuJoCo model)"
    vendor, model = "Beijing RobotEra Technology", "XBot-L"
    tags = ["humanoid", "xbot-l", "legged", "mujoco", "sim2sim", "simulation", "robot"]
    facts = [
        Fact("The repository is a reinforcement-learning framework based on NVIDIA Isaac Gym for humanoid "
             "locomotion that also integrates a sim-to-sim framework from Isaac Gym to MuJoCo", source="vendor_doc",
             ref=f"{README}:17"),
        Fact("The README documents the MuJoCo sim-to-sim run as python scripts/sim2sim.py --load_model "
             "/path/to/export/model.pt", source="vendor_doc", ref=f"{README}:126-130"),
        Fact("setup.py declares isaacgym (preview4), mujoco==2.3.6 and mujoco-python-viewer in install_requires",
             source="upstream_code", ref=f"{SETUP}:43-52"),
        Fact("run_mujoco(policy, cfg) is the MuJoCo simulation loop", source="upstream_code", ref=f"{SCRIPT}:87"),
        Fact("run_mujoco loads the MJCF with mujoco.MjModel.from_xml_path(cfg.sim_config.mujoco_model_path), "
             "overwrites model.opt.timestep with cfg.sim_config.dt, creates MjData and calls mujoco.mj_step",
             source="upstream_code", ref=f"{SCRIPT}:98-101"),
        Fact("get_obs reads the orientation sensor (reordered to x, y, z, w) and the angular-velocity sensor",
             source="upstream_code", ref=f"{SCRIPT}:70-80"),
        Fact("Sim2simCfg selects resources/robots/XBot/mjcf/XBot-L-terrain.xml only with --terrain and "
             "resources/robots/XBot/mjcf/XBot-L.xml otherwise", source="upstream_code", ref=f"{SCRIPT}:178-182"),
        Fact("Sim2simCfg sets sim_duration 60 s, dt 0.001 s and decimation 10", source="upstream_code",
             ref=f"{SCRIPT}:183-185"),
        Fact("The loop computes PD torques, clips them to cfg.robot_config.tau_limit, writes them to data.ctrl and "
             "advances the model with mujoco.mj_step", source="upstream_code", ref=f"{SCRIPT}:155-160"),
        Fact("Sim2simCfg sets tau_limit to 200 for all twelve joints", source="upstream_code", ref=f"{SCRIPT}:190"),
        Fact("The MJCF root element declares the model XBot-L", source="upstream_code", ref=f"{MODEL}:1"),
        Fact("The model uses radians, resolves its meshes from ../meshes/, and its option element sets timestep "
             "0.001 s, 50 solver iterations, the PGS solver and gravity 0 0 -9.81", source="upstream_code",
             ref=f"{MODEL}:2-3"),
        Fact("The world contains a plane ground and a base_link body at 0 0 0.88 that carries three slide joints "
             "and one ball joint", source="upstream_code", ref=f"{MODEL}:157-168"),
        Fact("The left leg chain has six limited hinge joints, left_leg_roll_joint through left_ankle_roll_joint, "
             "each with its own range", source="upstream_code", ref=f"{MODEL}:394-431"),
        Fact("The right leg chain has six limited hinge joints, right_leg_roll_joint through right_ankle_roll_joint, "
             "each with its own range", source="upstream_code", ref=f"{MODEL}:444-481"),
        Fact("The actuator section declares twelve motor actuators, one per leg hinge, each with ctrllimited true "
             "and ctrlrange -200 200", source="upstream_code", ref=f"{MODEL}:497-510"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step, the determinism kind and the lockstep clock; the members below make the whole contract readable
    #: in one place.
    fidelity = {
        "engine": "mujoco:XBot-L",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates the fixed model deterministically from the model defaults; the bridge accepts "
                     "a seed in cap.world.reset.v1 but a MuJoCo reset restores the model defaults and does not use "
                     "it, so one control sequence repeats a trajectory on the same engine.  The package's stand-in "
                     "is deterministic too, but its placeholder motion is not the engine's physics.",
        },
        "timestep_ms": 1.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the MJCF for the three "
            "base slides, the base ball joint, the twelve actuated leg hinges, their explicit ctrlranges and the "
            "0.001 s option step, then gives each actuated hinge a placeholder velocity proportional to its control "
            "value and holds the base where the model puts it; it computes no inertia, torque, gravity, contact, "
            "friction, constraint, damping or actuator dynamics and produces no MuJoCo trajectory",
            "the stand-in loads no STL mesh or texture and resolves no collision or contact; the model's ground "
            "plane, base collision geoms and armature attributes are not applied",
            "the upstream sim2sim loop overwrites the model step with its own 0.001 s dt (the same value the MJCF "
            "states), computes PD torques from a TorchScript policy and writes them to data.ctrl; this package does "
            "not run that loop and takes the control vector directly from the caller",
            "the upstream loop also builds its observation from the orientation and angular-velocity sensors, the "
            "joint arrays and the previous action; this package publishes the bridge's world state instead and does "
            "not model those sensors",
            "the fake reset restores the parsed model qpos0 and zeros; a real MjData reset also restores the full "
            "integration state, which this package did not inspect",
            "the real mujoco path (a backend name that backends does not list) was not run for this package, so no "
            "trajectory was compared with the engine and no physical XBot-L was involved",
        ],
    }
