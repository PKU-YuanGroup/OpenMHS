"""OpenMHS driver for gh.auturbo/stridesim: the ANYmal-D flat velocity-tracking Gymnasium task.

StrideSim registers Isaac Lab Gymnasium environments in the ``rl`` package.  The task card names the flat and
rough environment-config classes as its entry symbols; this package serves the flat task
``Template-Isaac-Velocity-Flat-Anymal-D-v0``, whose config is ``AnymalDFlatEnvCfg``.  A GymnasiumDriver is
configuration only: ``env_id`` names the environment, ``native`` names the config class the card confirmed, and the
bridge derives the whole ``cap.world.*`` contract from the environment's spaces.  ``cap.world.step.v1`` takes
``{ticks, action}`` with the action shaped by the action space, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` takes ``{seed}``.

The upstream environment needs Isaac Sim 4.0.0 and Isaac Lab v1.0.0 with a GPU (README.md:30-32) and is not
importable where the gate runs, so the ``fake`` backend is the package's own pure Python kinematic stand-in
(fake.py).  Nothing here imports or runs the clone.  A backend name that ``backends`` does not list (``sim``) would
be served by ``gymnasium.make(env_id)`` through ``GymnasiumDriver.open_native``; that path needs the upstream stack
and was not run here.

The device is simulated (R0): there is no hardware backend, no physical stop and no operator-required limit.  The
``fidelity`` attribute is the contract of the model as deployed on the fake backend (spec 05-fidelity FID-002):
a kinematic stand-in (F0), not the Isaac Sim physics model, and its gaps say so.  Every fact cites a line of the
clone at commit d941ee93cec051c9455cf0c699384fd5410d4d3f.  This package is model-authored and unreviewed; it is
checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

FLAT = "rl/StrideSim_RL/tasks/locomotion/velocity/config/anymal_d/flat_env_cfg.py"
ROUGH = "rl/StrideSim_RL/tasks/locomotion/velocity/config/anymal_d/rough_env_cfg.py"
VELOCITY = "rl/StrideSim_RL/tasks/locomotion/velocity/velocity_env_cfg.py"
REGISTER = "rl/StrideSim_RL/tasks/locomotion/velocity/config/anymal_d/__init__.py"
ANYMAL = "exts/StrideSim/StrideSim/anymal_articulation.py"


class AnymalDVelocity(GymnasiumDriver):
    device_id = "anymal_d_velocity"
    env_id = "Template-Isaac-Velocity-Flat-Anymal-D-v0"
    native = "StrideSim_RL.tasks.locomotion.velocity.config.anymal_d.flat_env_cfg:AnymalDFlatEnvCfg"
    backends = {"fake": ".fake:FakeAnymalDEnv"}
    display_name = "StrideSim ANYmal-D flat velocity tracking (Isaac Lab task)"
    vendor, model = "AuTURBO StrideSim", "ANYmal-D"
    tags = ["anymal", "anymal-d", "isaac-lab", "isaac-sim", "locomotion", "velocity-tracking",
            "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The flat task inherits the rough task and changes the terrain to a plane, removes the height scanner "
             "and the height_scan observation and disables the terrain-level curriculum", source="upstream_code",
             ref=f"{FLAT}:7-23"),
        Fact("The rough task sets the scene robot to ANYMAL_D_CFG", source="upstream_code", ref=f"{ROUGH}:17"),
        Fact("The velocity commands are sampled from -1.0 to 1.0 for linear x, linear y and angular z, with heading "
             "from -pi to pi", source="upstream_code", ref=f"{VELOCITY}:99"),
        Fact("The policy action is a joint-position action over all joints with scale 0.5 and the default joint "
             "offset", source="upstream_code", ref=f"{VELOCITY}:108"),
        Fact("The ANYmal-D articulation sample uses 12 joint positions, 12 joint velocities and 12 previous-action "
             "values, and its policy observation is a 235-value vector that includes a height scan",
             source="upstream_code", ref=f"{ANYMAL}:88-159"),
        Fact("The flat task removes the height_scan observation term", source="upstream_code", ref=f"{FLAT}:21"),
        Fact("In the base configuration, the policy observation terms are base linear velocity, base angular "
             "velocity, projected gravity, velocity commands, joint positions, joint velocities, the last action "
             "and the height scan", source="upstream_code", ref=f"{VELOCITY}:120-133"),
        Fact("The policy observation terms are concatenated into one array and observation corruption is enabled "
             "in the base configuration", source="upstream_code", ref=f"{VELOCITY}:138-139"),
        Fact("The simulation advances by 0.005 s per physics step, the control decimation is 4 and an episode is "
             "20.0 s long", source="upstream_code", ref=f"{VELOCITY}:295-298"),
        Fact("The flat task is registered as Template-Isaac-Velocity-Flat-Anymal-D-v0 with the external entry point "
             "omni.isaac.lab.envs:ManagerBasedRLEnv and the AnymalDFlatEnvCfg config", source="upstream_code",
             ref=f"{REGISTER}:9-15"),
        Fact("The upstream project requires Isaac Sim 4.0.0 and Isaac Lab v1.0.0", source="vendor_doc",
             ref="README.md:30-32"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The fake is kinematic, so the
    #: level is F0; the bridge derives the engine, clock and lockstep members and they are written out here.
    fidelity = {
        "engine": "isaac:Template-Isaac-Velocity-Flat-Anymal-D-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's command draw and the kinematic update is "
                     "deterministic, so one seed and action sequence repeat a trajectory; the upstream Isaac Lab "
                     "and PhysX random streams are not used and no trajectory was compared with the upstream "
                     "environment",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic model: no rigid-body dynamics, contacts, friction, actuator, sensor, terrain or noise model; "
            "the fake integrates a base velocity directly from the action",
            "the fake uses the flat task's 12 action values and 48 observation values (the 235-value ANYmal-D "
            "sample observation without its height scan; flat_env_cfg.py:21), but the values are synthetic: joint "
            "positions, joint velocities and the previous action are placeholders, projected gravity is fixed, the "
            "base pose is not observed and the action space is unbounded because the real bound is outside the clone",
            "the upstream simulator needs Isaac Sim 4.0.0 and Isaac Lab v1.0.0 with a GPU (README.md:30-32) and "
            "was not run; no trajectory was compared with it",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "the height scan, rough terrain, contacts, push events, actuator dynamics and PhysX physics are not "
            "modelled; the rough task's 235-value observation is not served",
            "snapshot and restore are not offered: the fake exposes no get_state or set_state",
        ],
    }
