"""OpenMHS driver for gh.openai/mujoco-worldgen: the ``particle`` MJCF model as a MuJoCo world.

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's primary model
(``assets/xmls/particle/main.xml``) and the bridge derives the contract from the model it loads.
``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``; the bridge writes ``data.ctrl`` and
runs ``mj_step`` ``ticks`` times.  The model declares two motor actuators but no ``ctrlrange``: it
bounds no control value itself, so the bridge publishes ``action.ctrl`` as ``operator_required``: the endpoint refuses a step that sets
it (``MHS.SAFETY.LIMITS_UNSET``, before any native call) until the site's ``site-limits.json`` bounds it;
``site-limits.example.json`` is operator example data, not a bound of the model.
``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` + ``mj_forward``.  The world
state is the bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``,
``timestep_ms``, ``seed``).  The device is simulated (R0): there is no hardware backend and no native
stop.

The upstream repository builds randomized worlds around ``mujoco-py`` 1.50 (README.md:3-7, :13,
requirements.txt:7) and maps the action vector onto ``sim.data.ctrl`` (sim_funcs.py:12-25).  This
package serves the card's ``models[0]`` directly as a MuJoCo model, not the world-generation layer;
the card's second model (``assets/xmls/particle_hinge/main.xml``) is not served.

MuJoCo is not installed where the gate runs, so ``backends["fake"]`` is this package's stand-in
``mujoco`` module (fake.py).  It reads the same model file for the actuator count, the joint
dimensions and the option time step, but its integration is a placeholder, not MuJoCo's physics; the
fidelity ``gaps`` list every difference.  A backend name that ``backends`` does not list (``sim``)
imports the real ``mujoco`` module and loads the same model file; that path was not run here.  Every
Fact cites a line of the clone at commit 39f52b1b47aed499925a6a214b58bdbdb4e2f75e.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/.
MODEL = "assets/xmls/particle/main.xml"
MODEL_PATH = "../../../../robots/openai/mujoco-worldgen/" + MODEL


class WorldgenParticle(MujocoDriver):
    device_id = "worldgen-particle"
    model_path = MODEL_PATH
    backends = {"fake": fake_mujoco}
    display_name = "MuJoCo Worldgen particle (MuJoCo simulation)"
    vendor, model = "OpenAI", "worldgen particle"
    tags = ["mujoco", "particle", "reinforcement-learning", "robot", "simulation", "worldgen"]
    facts = [
        Fact("The card's primary model is assets/xmls/particle/main.xml: its root is a <mujoco> element whose "
             "worldbody contains the body 'particle' with three slide joints named slide0, slide1 and slide2 on "
             "the x, y and z axes", source="upstream_code", ref=f"{MODEL}:2-8"),
        Fact("The model's <option> element sets the integration timestep to 0.005 s", source="upstream_code",
             ref=f"{MODEL}:3"),
        Fact("slide0 and slide1 have damping 0.1, while slide2 has damping 10000", source="upstream_code",
             ref=f"{MODEL}:6-8"),
        Fact("The particle body has a sphere geom of mass 1, half-size 0.15 and position 0 0 0", source="upstream_code",
             ref=f"{MODEL}:9"),
        Fact("The model declares two <motor> actuators with gear 100 on slide0 and slide1, and neither actuator "
             "states a ctrlrange, so the model file gives the two controls no limit", source="upstream_code",
             ref=f"{MODEL}:16-19"),
        Fact("The README says actions in the action_space are all actuators of objects added during world building, "
             "and names ObjFromXML('particle') as an object with actuators", source="vendor_doc", ref="README.md:7"),
        Fact("The README states that worldgen uses meters, kilograms and radians, with angles in [-pi, pi]",
             source="vendor_doc", ref="README.md:33"),
        Fact("The README says the repository requires the MuJoCo physics engine, was tested with MuJoCo 1.50 and "
             "installs through mujoco-py", source="vendor_doc", ref="README.md:13"),
        Fact("requirements.txt pins mujoco-py to >=1.50.1 and <1.50.2", source="upstream_code",
             ref="requirements.txt:7"),
        Fact("The repository is archived and its code is provided as-is with no updates expected",
             source="vendor_doc", ref="README.md:1"),
        Fact("The simple_particle example loads the 'particle' object with ObjFromXML and builds a 4 x 4 x 2.5 world",
             source="upstream_code", ref="examples/simple_particle.py:13-17"),
        Fact("The simple_particle example runs the environment with horizon 30", source="upstream_code",
             ref="examples/simple_particle.py:25"),
        Fact("ctrl_set_action copies a torque actuator's action into sim.data.ctrl, and adds the current qpos for a "
             "position actuator", source="upstream_code", ref="mujoco_worldgen/util/sim_funcs.py:12-25"),
        Fact("When no explicit action bounds are given, Env's action space has nmocap * 7 + model.nu entries",
             source="upstream_code", ref="mujoco_worldgen/env.py:241-243"),
        Fact("Env.step clamps the action to the action space, calls set_action and then sim.step",
             source="upstream_code", ref="mujoco_worldgen/env.py:346-354"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind, the time step and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:worldgen-particle",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "the model starts from the MJCF defaults and MuJoCo integrates deterministically; the bridge "
                     "accepts cap.world.reset.v1 seed for the class contract but mj_resetData does not use it, so no "
                     "seed selects a different state",
        },
        "timestep_ms": 5.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the model file for the two "
            "actuators, the three slide joints and the 0.005 s timestep, but integrates a placeholder joint motion "
            "proportional to each control value, so trajectories, damping, gear forces and actuator dynamics are "
            "not MuJoCo's",
            "the stand-in resolves no contact, constraint or friction (the model's only geom contact is the mass-1 "
            "sphere against the mass-0 outer-bound box) and loads no rendering context",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "the upstream world-generation layer (WorldBuilder, placements, randomization) and the Env wrapper are "
            "not part of this driver: it serves the bare MJCF model and its ctrl vector, not a generated world or a "
            "Gym environment",
            "the card's second model (assets/xmls/particle_hinge/main.xml) is not served: one package serves one "
            "device, and this driver uses the card's models[0]",
            "no physical device is modelled and nothing was validated against hardware",
        ],
    }
