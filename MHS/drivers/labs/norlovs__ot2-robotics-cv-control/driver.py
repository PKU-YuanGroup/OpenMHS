"""OpenMHS driver for gh.norlovs/ot2-robotics-cv-control: the OT-2 pipetting-robot digital twin (a Gymnasium family driver).

The upstream entry point ``src.ot2.ot2_gym_wrapper:OT2Env`` (ot2_gym_wrapper.py:7) is a Gymnasium environment over
the repository's PyBullet digital twin (sim_class.py:12).  The twin is simulated (R0): there is no hardware backend,
no physical stop path and no operator-required bound.  ``GymnasiumDriver`` is configuration only: the bridge derives
the ``cap.world.step.v1`` action schema from the environment's action space (three velocities in [-1, 1],
ot2_gym_wrapper.py:26-30) and serves ``cap.world.reset.v1`` and ``cap.world.seed.v1``; the observation is six values
(ot2_gym_wrapper.py:31-33).

The gate cannot import gymnasium or pybullet (neither is installed where it runs; requirements.txt:1-17 lists both),
so the ``fake`` backend is the package's own pure Python kinematic stand-in (fake.py).  The upstream environment was
not run here.  The fidelity contract is the contract of the model as deployed (spec 05-fidelity FID-002): the fake is
kinematic (F0), has no simulated clock and no physics, and its gaps say what is not modelled.

Every Fact cites a line of the clone at the pinned commit (a0a621e5a79c32e70c8c97864d256693d3b3eac0).  This package
is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

WRAPPER = "src/ot2/ot2_gym_wrapper.py"
SIM = "src/ot2/sim_class.py"


class OT2DigitalTwin(GymnasiumDriver):
    device_id = "ot2-twin"
    native = "src.ot2.ot2_gym_wrapper:OT2Env"
    backends = {"fake": ".fake:FakeOT2Env"}
    action_space_ref = f"{WRAPPER}:26-30"
    display_name = "OT-2 pipetting-robot digital twin (OT2Env)"
    vendor, model = "norlovs", "OT-2 Robotics CV Control"
    tags = ["ot-2", "opentrons", "digital-twin", "pipetting", "pybullet", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("OT2Env is a Gymnasium environment wrapper for the OT-2 pipetting robot digital twin",
             source="upstream_code", ref=f"{WRAPPER}:9"),
        Fact("The observation is [pipette_x, pipette_y, pipette_z, goal_x, goal_y, goal_z]", source="upstream_code",
             ref=f"{WRAPPER}:10"),
        Fact("The action is [vx, vy, vz] continuous velocities in [-1, 1]", source="upstream_code",
             ref=f"{WRAPPER}:11"),
        Fact("The reward is the negative Euclidean distance to the goal with a +10 bonus on success",
             source="upstream_code", ref=f"{WRAPPER}:12"),
        Fact("The action space is Box(low=[-1, -1, -1], high=[1, 1, 1])", source="upstream_code",
             ref=f"{WRAPPER}:26-30"),
        Fact("The observation space is Box(shape=(6,)) with unbounded low and high", source="upstream_code",
             ref=f"{WRAPPER}:31-33"),
        Fact("The goal sampling bounds are x [-0.1875, 0.2535], y [-0.1705, 0.2195], z [0.1196, 0.2895]",
             source="upstream_code", ref=f"{WRAPPER}:16-17"),
        Fact("A reset seeds numpy when a seed is given, resets the simulation and draws the goal uniformly between "
             "_LOW and _HIGH", source="upstream_code", ref=f"{WRAPPER}:38-49"),
        Fact("A step runs the simulation with the action plus a drop flag of 0 and re-reads the pipette position",
             source="upstream_code", ref=f"{WRAPPER}:55-59"),
        Fact("A distance below 0.01 terminates the episode and adds 10 to the reward", source="upstream_code",
             ref=f"{WRAPPER}:63-71"),
        Fact("The episode truncates when the step counter reaches max_steps", source="upstream_code",
             ref=f"{WRAPPER}:73-74"),
        Fact("The info dictionary reports current_position, target_position and distance_to_goal",
             source="upstream_code", ref=f"{WRAPPER}:76-80"),
        Fact("The OT-2 digital twin runs in PyBullet", source="vendor_doc", ref="README.md:165"),
        Fact("The twin connects PyBullet in GUI mode when render is true and in DIRECT mode otherwise",
             source="upstream_code", ref=f"{SIM}:16-21"),
        Fact("The twin loads the simulated robot from ot_2_simulation_v6.urdf", source="upstream_code",
             ref=f"{SIM}:109-111"),
        Fact("The pipette position is the robot base position minus the joint positions plus the pipette offset",
             source="upstream_code", ref=f"{SIM}:173-186"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: determinism kind and lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "pybullet:OT-2-digital-twin",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) fixes the goal draw and the fake's position update is deterministic, so one seed "
                     "and one action sequence repeat a trajectory; upstream seeds numpy's global generator and runs "
                     "PyBullet on its own clock, so a seed does not repeat a trajectory across the two",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is kinematic: one direct position update per transition, not PyBullet rigid-body dynamics, "
            "contacts, friction, forces or the simulation clock; no actuator, sensor or noise model",
            "no simulated time base: timestep_ms is 0 and a step is one discrete transition, not a physical duration",
            "the PyBullet GUI/DIRECT renderer is not modelled: render() is a no-op",
            "the upstream environment was not run (gymnasium and pybullet are not installed where the gate ran), so "
            "the fake was never compared with it; the goal draw uses random.Random, upstream numpy's global generator",
            "observations are Python lists of floats, upstream returns float32 numpy arrays and rounds the pipette "
            "position to four decimals",
            "reset accepts only seed, like the upstream signature; cap.world.reset.v1 options are not supported and "
            "the bridge falls back to a seedless reset when options are supplied",
            "no droplet, specimen or plate physics is modelled",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
