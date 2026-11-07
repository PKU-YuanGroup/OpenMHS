"""OpenMHS driver for gh.noetix-robotics/noetix_n2_gym: the Noetix N2 humanoid MJCF as a MuJoCo world.

The card's upstream entry symbol is ``sim2sim.sim2sim:run_mujoco`` (``sim2sim/sim2sim.py:53``): a MuJoCo sim2sim loop
that reads a YAML config, loads an MJCF with ``mujoco.MjModel.from_xml_path``, loads a TorchScript policy, computes PD
torques and calls ``mujoco.mj_step``.  The loop exposes no reset, step or seed of its own and imports the Isaac Gym
training package (``humanoid``) and a keyboard listener, so this package serves the documented sim2sim model instead
of importing or running that script.

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's model and the bridge derives the contract
from the file it loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``, checks each ``ctrl`` element
against the model's ``actuator_ctrlrange`` when the model declares one, writes ``data.ctrl`` and runs ``mj_step``
``ticks`` times.  ``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` + ``mj_forward``.  The
world state is the bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``,
``timestep_ms``, ``seed``).

The served file is the card's ``models[1]``, ``resources/robots/N2/mjcf/n2_18dof.xml``: ``README.md:59`` tells the
sim2sim user to update ``sim2sim/configs/n2_18dof.yaml`` and that config selects this model (``n2_18dof.yaml:3``).
The script's own default config is ``n2_10dof.yaml`` (``sim2sim.py:176``), an inconsistency of the clone noted in
``RESULT.json``; the 18-dof model is the one the README's sim2sim procedure documents.  Both files are listed in the
card's ``models``.

The device is simulated (R0, ``world.sim``): there is no hardware backend and no physical stop.  The MJCF declares
eighteen motor actuators but no ``ctrlrange`` or ``ctrllimited`` attribute (``n2_18dof.xml:169-191``),
so the bridge publishes ``action.ctrl`` as ``operator_required``: the endpoint refuses a step that sets
it (``MHS.SAFETY.LIMITS_UNSET``, before any native call) until the site's ``site-limits.json`` bounds it;
``site-limits.example.json`` is operator example data, not a bound of the model; the driver invents none.  MuJoCo is not
installed where the acceptance gate runs (no network, no pip), so ``backends["fake"]`` is this package's stand-in
``mujoco`` module (fake.py).  It parses the same file for the free base, the eighteen hinge joints and the eighteen
actuators, but its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` list every difference.
A backend name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same file;
that path was not run here.  This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "resources/robots/N2/mjcf/n2_18dof.xml"
CONFIG = "sim2sim/configs/n2_18dof.yaml"
SCRIPT = "sim2sim/sim2sim.py"
README = "README.md"
SETUP = "setup.py"
#: The card's models[1], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/noetix-robotics/noetix_n2_gym/" + MODEL


class N2(MujocoDriver):
    device_id = "n2-18dof"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Noetix N2 humanoid, 18-DoF MuJoCo model"
    vendor, model = "Noetix Robotics", "N2"
    tags = ["noetix", "n2", "humanoid", "legged", "mujoco", "simulation", "robot"]
    facts = [
        Fact("The README's sim-to-sim procedure tells the user to update the policy_config in "
             "sim2sim/configs/n2_18dof.yaml before starting the MuJoCo deployment", source="vendor_doc",
             ref=f"{README}:59"),
        Fact("The README labels the deployment MuJoCo-based sim-to-sim and gives python sim2sim/sim2sim.py as the "
             "command", source="vendor_doc", ref=f"{README}:60-63"),
        Fact("The sim2sim config selects resources/robots/N2/mjcf/n2_18dof.xml as the model", source="upstream_code",
             ref=f"{CONFIG}:3"),
        Fact("The sim2sim config sets simulation_dt to 0.002 s and control_decimation to 10", source="upstream_code",
             ref=f"{CONFIG}:8-10"),
        Fact("run_mujoco opens the YAML config named by its cfg argument and resolves its xml_path",
             source="upstream_code", ref=f"{SCRIPT}:65-68"),
        Fact("run_mujoco loads the robot model with mujoco.MjModel.from_xml_path(xml_path)", source="upstream_code",
             ref=f"{SCRIPT}:90"),
        Fact("run_mujoco overwrites model.opt.timestep with the config's simulation_dt and then creates MjData",
             source="upstream_code", ref=f"{SCRIPT}:91-92"),
        Fact("run_mujoco computes PD torques and writes the torque vector to data.ctrl", source="upstream_code",
             ref=f"{SCRIPT}:159-161"),
        Fact("run_mujoco advances the simulation with mujoco.mj_step(model, data)", source="upstream_code",
             ref=f"{SCRIPT}:163"),
        Fact("The script's __main__ block defaults the config file to n2_10dof.yaml", source="upstream_code",
             ref=f"{SCRIPT}:176"),
        Fact("The MJCF root element declares the model N2", source="upstream_code", ref=f"{MODEL}:1"),
        Fact("The model uses radians and resolves its meshes from ../meshes/", source="upstream_code",
             ref=f"{MODEL}:2"),
        Fact("The default joint class sets damping 0.001, armature 0.01 and frictionloss 0.1", source="upstream_code",
             ref=f"{MODEL}:4-6"),
        Fact("The base_link body is placed at 0 0 0.75 and carries the free joint named root", source="upstream_code",
             ref=f"{MODEL}:43-47"),
        Fact("Eighteen limited hinge joints carry the arms and legs: four per arm and five per leg, each with its own "
             "range", source="upstream_code", ref=f"{MODEL}:52-156"),
        Fact("The actuator section declares eighteen motor actuators, one per hinge joint", source="upstream_code",
             ref=f"{MODEL}:169-191"),
        Fact("No actuator element sets ctrlrange or ctrllimited, so the model states no control range for any motor",
             source="upstream_code", ref=f"{MODEL}:169-191"),
        Fact("The package declares mujoco==2.3.6 and mujoco-python-viewer in install_requires", source="upstream_code",
             ref=f"{SETUP}:20-22"),
        Fact("The package declares isaacgym (preview 4) in install_requires", source="upstream_code",
             ref=f"{SETUP}:12"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind, the time step and the lockstep clock; the members below make the whole contract readable
    #: in one place.  The file declares no <option timestep>, so the stand-in uses MuJoCo's 2 ms default, the same
    #: value the upstream config sets (n2_18dof.yaml:8) and run_mujoco overwrites (sim2sim.py:91).
    fidelity = {
        "engine": "mujoco:N2",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates a fixed model deterministically from the model defaults; cap.world.reset.v1 "
                     "restores those defaults and the bridge's seed input is accepted for the class contract but a "
                     "MuJoCo reset does not use it.  The package's stand-in is deterministic too, but its placeholder "
                     "motion is not the engine's physics.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the MJCF for the free base, "
            "the eighteen hinge joints, the eighteen motor actuators and the option time step, then gives each "
            "actuated hinge a placeholder velocity proportional to its control value and holds the free base where "
            "the model puts it; it computes no inertia, torque, gravity, contact, friction, constraint, damping or "
            "actuator dynamics and produces no MuJoCo trajectory",
            "the stand-in loads no STL mesh or texture and resolves no collision or contact, so the model's floor, "
            "base collision geoms and armature attributes are not applied",
            "the model's sensor section and sites (foot forces, IMU) are not read or exposed; the upstream loop "
            "reads the two foot-force sensors (sim2sim.py:148-155), but this package serves only the bridge's "
            "integration state",
            "the model declares no ctrlrange or ctrllimited for its motors, "
            "so the bridge publishes action.ctrl operator_required: a step that sets it is refused until the site's site-limits.json bounds it, and site-limits.example.json is operator example data, not a model bound; the upstream sim2sim loop clips no torque either and writes the PD "
            "result to data.ctrl",
            "the model states no <option timestep>, so the stand-in uses the 2 ms MuJoCo library default; the "
            "upstream sim2sim loop overwrites the model step with its config's 0.002 s (n2_18dof.yaml:8, "
            "sim2sim.py:91), which is this package's published timestep",
            "the upstream sim2sim loop drives the model with a TorchScript policy and a keyboard command object; "
            "this package serves the model alone and takes the control vector from the caller",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared with "
            "the real engine",
            "snapshot and restore fall back to copying time, qpos, qvel and ctrl because the stand-in implements no "
            "mj_getState/mj_setState, so a restore is not exact",
            "no physical humanoid is modelled and nothing was validated against the N2 hardware",
        ],
    }
