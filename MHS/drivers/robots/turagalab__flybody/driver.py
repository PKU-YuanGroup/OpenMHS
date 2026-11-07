"""OpenMHS driver for gh.turagalab/flybody: the Drosophila fruit fly MuJoCo body model as a simulated world.

A MujocoDriver (configuration only) over the model file the repository builds, ``flybody/fruitfly/assets/fruitfly.xml``
(a 918-line MJCF model of the fly's body and its 78 actuators, with a free root joint).  The package carries that model
as ``model.xml`` and the bridge serves ``cap.world.step.v1`` and ``cap.world.reset.v1`` on it.

The card names the upstream simulator as the mock path.  The MuJoCo engine is not installed where the gate runs, so the
fake backend is a stand-in ``mujoco`` module (``fake.py``): it reads the integration step, the dimension counts and the
actuator control ranges of ``model.xml`` and advances a minimal state, and it does not reproduce the engine's dynamics.
The step limits are the model's own ``ctrlrange`` per actuator: the main default makes every actuator ctrl-limited
(``fruitfly.xml:11``) and the classes give the ranges.  The fidelity ``gaps``
below state every difference, including that the model's 80 mesh assets are not carried.

Every Fact cites a line of the clone at the pinned commit (d015e9bfe441bd90ae431bac24c55cb74bdbce26).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco


class FlyBody(MujocoDriver):
    device_id = "flybody"
    model_path = "model.xml"
    backends = {"fake": fake_mujoco}
    display_name = "FlyBody fruit fly MuJoCo model"
    vendor, model = "Turaga Lab", "Drosophila melanogaster body model (fruitfly.xml)"
    tags = ["mujoco", "fruit-fly", "drosophila", "biomechanics", "simulation"]
    facts = [
        Fact("The model sets its integration step to 0.0001 s, gravity (0, 0, -981), density 0.00128 and viscosity "
             "0.000185", source="upstream_code", ref="flybody/fruitfly/assets/fruitfly.xml:4"),
        Fact("The environment loads the model from assets/fruitfly.xml (the file this package carries as model.xml)",
             source="upstream_code", ref="flybody/fruitfly/fruitfly.py:21"),
        Fact("The floor scene includes fruitfly.xml and adds a 5 by 5 plane floor at z -0.132",
             source="upstream_code", ref="flybody/fruitfly/assets/floor.xml:10-13"),
        Fact("The walker spawns at (0, 0, 0.1278) m", source="upstream_code",
             ref="flybody/fruitfly/fruitfly.py:23"),
        Fact("The action groups are adhesion, head, mouth, antennae, wings, abdomen, legs and user, each disabled "
             "until it is enabled", source="upstream_code", ref="flybody/fruitfly/fruitfly.py:24-32"),
        Fact("The root body carries the free joint named 'free'", source="upstream_code",
             ref="flybody/fruitfly/assets/fruitfly.xml:309"),
        Fact("The actuator section declares the model's actuators as general and adhesion elements",
             source="upstream_code", ref="flybody/fruitfly/assets/fruitfly.xml:819-898"),
        Fact("The default section scales the meshes by 0.1 and gives the geoms friction 0.5",
             source="upstream_code", ref="flybody/fruitfly/assets/fruitfly.xml:9-10"),
        Fact("The main default class makes every general actuator ctrl-limited", source="upstream_code",
             ref="flybody/fruitfly/assets/fruitfly.xml:11"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until mhs.safety.reset "
                  "clears the latch, and the world state stays readable")

    #: The fidelity contract as deployed on the fake backend.  It states every difference from the MuJoCo engine and
    #: from the upstream environment rather than hiding them behind the derived defaults.
    fidelity = {
        "engine": "mujoco",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "the stand-in state is deterministic; a real MuJoCo run of the model was never made, and the "
                     "bridge's seed is only recorded, it does not randomise the model's initial state",
        },
        "timestep_ms": 0.1,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in mujoco module, not the MuJoCo engine: it parses the integration step and "
            "the joint and actuator counts of model.xml and advances time (qpos follows qvel, which stays zero); it "
            "computes no equations of motion, contacts, adhesion or actuator dynamics, so a ctrl vector changes "
            "nothing in it",
            "the package carries the model XML only (918 lines); the 80 mesh assets the XML references (.obj files, "
            "about 154 MB in flybody/fruitfly/assets) are not carried, so a real MuJoCo load needs that assets "
            "directory beside model.xml",
            "the stand-in resolves each actuator's ctrlrange and ctrllimited from model.xml's default classes as the "
            "MJCF rules say (fruitfly.xml:11 makes every actuator ctrl-limited), so action.ctrl is bounded per "
            "actuator by the model's ranges; that resolution is the stand-in's, not MuJoCo's compiler",
            "the clone's environment is a dm_control composer walker (flybody/fruitfly/fruitfly.py) with "
            "observations, rewards and termination; this package serves the raw model, not that environment, and the "
            "dm_control stack is not carried",
            "snapshot and restore use the bridge's copied time/qpos/qvel/ctrl fallback, not mjSTATE_INTEGRATION",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the model's timestep only",
            "the fly model was never validated against a physical fly or against the upstream environment",
        ],
    }
