"""OpenMHS driver for gh.peterxjerk/livelybot_rl_control: the Pai 12-DoF MJCF as a MuJoCo world.

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's primary model
(``resources/robots/pai_12dof/mjcf/pai_12dof.xml``) and the bridge derives the whole contract from the model it
loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``; each ``ctrl`` element is checked against the
model's ``actuator_ctrlrange`` (one element per motor actuator) before it is written to ``data.ctrl``, then
``mj_step`` runs ``ticks`` times.  ``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` +
``mj_forward``.  The world state is the bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``,
``tick``, ``timestep_ms``, ``seed``).  The device is simulated (R1, the spec's class for simulation stepping): there
is no hardware backend and no operator-required limit; the model's control ranges are derived from the MJCF itself.

The upstream repository is an Isaac Gym training environment with a MuJoCo sim-to-sim script (README.md:3,
README.md:67).  ``humanoid/scripts/sim2sim.py:89`` defines ``run_mujoco(policy, cfg)``; it loads an MJCF with
``mujoco.MjModel.from_xml_path`` (line 100), creates ``mujoco.MjData`` (line 102) and steps it with
``mujoco.mj_step`` (line 172).  Importing that module also imports ``humanoid.envs``, which imports Isaac Gym
(``humanoid/envs/base/legged_robot.py:36-37``), so this package serves the model itself rather than the script.

The model file is read from the read-only clone at the pinned commit (it is never copied into this package and never
imported).  ``mujoco`` is not installed where the gate runs (``setup.py:43-51`` lists ``mujoco==2.3.6`` among the
upstream dependencies), so ``backends["fake"]`` is this package's stand-in ``mujoco`` module (``fake.py``).  It reads
the same model file for the actuator count, the control ranges, the joint dimensions and the option time step, but
its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` list every difference.  A backend name
that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same model file; that path
was not run here.  Every Fact below cites a line of the clone at commit
``86b2e85a2e6093e478dea8c8a48bbe4adbfc7445``.  This package is model-authored and unreviewed: it is checked on the
fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

MODEL = "resources/robots/pai_12dof/mjcf/pai_12dof.xml"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/peterxjerk/livelybot_rl_control/" + MODEL


class Pai12Dof(MujocoDriver):
    device_id = "pai-12dof"
    model_path = MODEL_PATH
    backends = {"fake": fake_mujoco}
    display_name = "Pai 12-DoF humanoid (MuJoCo simulation)"
    vendor, model = "HighTorque", "Pai 12-DoF (pai_12dof_v2_0312)"
    tags = ["pai", "12-dof", "humanoid", "mujoco", "simulation", "reinforcement-learning", "livelybot"]
    #: Simulated stepping of a legged robot is R1 in MHS/spec/04-safety.md section 2.1 (simulation stepping).
    risk = "R1"
    facts = [
        Fact("The repository is an Isaac Gym reinforcement learning environment for HighTorque's legged robot and "
             "also integrates a sim-to-sim framework from Isaac Gym to MuJoCo", source="vendor_doc",
             ref="README.md:3"),
        Fact("The README describes the MuJoCo-based sim-to-sim deployment as running humanoid/scripts/sim2sim.py "
             "with an exported policy", source="vendor_doc", ref="README.md:67-69"),
        Fact("The sim-to-sim entry point is the module-level function run_mujoco(policy, cfg)", source="upstream_code",
             ref="humanoid/scripts/sim2sim.py:89"),
        Fact("run_mujoco loads the model with mujoco.MjModel.from_xml_path, overrides model.opt.timestep with the "
             "configured dt, creates mujoco.MjData and calls mujoco.mj_step once before the loop", source="upstream_code",
             ref="humanoid/scripts/sim2sim.py:100-103"),
        Fact("Every loop iteration writes the clipped PD torques to data.ctrl and advances the model with "
             "mujoco.mj_step", source="upstream_code", ref="humanoid/scripts/sim2sim.py:161-172"),
        Fact("Sim2simCfg sets sim_config.dt to 0.001 s and sim_duration to 60.0 s, with decimation 10", source="upstream_code",
             ref="humanoid/scripts/sim2sim.py:195-197"),
        Fact("The default non-terrain model path ends at resources/robots/pai_12dof/mjcf/pai_12dof without the .xml "
             "extension, so an importing caller must supply the explicit file path", source="upstream_code",
             ref="humanoid/scripts/sim2sim.py:194"),
        Fact("The MuJoCo model is declared as pai_12dof_v2_0312", source="upstream_code",
             ref="resources/robots/pai_12dof/mjcf/pai_12dof.xml:1"),
        Fact("The model sets the physics timestep to 0.001 s", source="upstream_code",
             ref="resources/robots/pai_12dof/mjcf/pai_12dof.xml:3"),
        Fact("The default block makes joints limited and motors control-limited unless an element overrides it",
             source="upstream_code", ref="resources/robots/pai_12dof/mjcf/pai_12dof.xml:13-16"),
        Fact("The base is floating: the base_link body carries three slide joints and one ball joint", source="upstream_code",
             ref="resources/robots/pai_12dof/mjcf/pai_12dof.xml:68-71"),
        Fact("The two legs carry twelve named hinge joints with per-joint ranges on the cited lines", source="upstream_code",
             ref="resources/robots/pai_12dof/mjcf/pai_12dof.xml:80-141"),
        Fact("The actuator section declares twelve motor actuators, one per leg joint, each with "
             "ctrllimited=true and ctrlrange -200 to 200", source="upstream_code",
             ref="resources/robots/pai_12dof/mjcf/pai_12dof.xml:153-164"),
        Fact("setup.py install_requires lists isaacgym, mujoco==2.3.6, mujoco-python-viewer and the training stack; "
             "there is no serial, USB or VISA dependency", source="upstream_code", ref="setup.py:43-51"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The upstream MJCF is a
    #: rigid-body model that real MuJoCo would integrate as F1, but the delivered fake backend is an analytic
    #: stand-in with no contact or actuator dynamics, so the package declares F0 and discloses the difference.
    fidelity = {
        "engine": "mujoco:pai_12dof_v2_0312",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "the stand-in has no random draw and the bridge snapshots the whole integration state, so the "
                     "same controls reproduce the same trajectory; the real MuJoCo engine was not run",
        },
        "timestep_ms": 1.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a pure Python stand-in for the mujoco library: it parses the MJCF for the joint "
            "dimensions, the actuator control ranges and the option timestep, but its integration moves each "
            "actuated joint in proportion to its control value; it resolves no contact, friction, equality, tendon, "
            "actuator or sensor dynamics, so the deployed fake is F0 even though the MJCF and real MuJoCo would "
            "support F1",
            "no mesh or texture of the model's meshdir is loaded and the floating base is not integrated; a ball "
            "joint's quaternion is kept at its identity value and the base slides do not move",
            "MuJoCo itself was not importable where the gate ran, so no trajectory was compared with the real "
            "engine; the sim backend that imports mujoco was not run",
            "the upstream sim2sim loop also performs policy inference, observation stacking, PD torque computation "
            "and rendering (humanoid/scripts/sim2sim.py:116-176); this driver exposes only the MuJoCo ctrl vector "
            "and integration state",
            "the card's second model, resources/robots/pai_12dof/mjcf/pai_12dof_terrain.xml, is not served: one "
            "package serves the primary model (models[0])",
            "no physical Pai robot is modelled and nothing was validated against hardware",
        ],
    }
