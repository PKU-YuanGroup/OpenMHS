"""OpenMHS driver for gh.jacopopan/gym-marl-reconnaissance: the ReconArena multi-agent environment (a Gymnasium
family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
whole contract from the environment's action and observation spaces.  The default task_assignment world is one
Tello plus one RoboMaster against two adversaries and one neutral agent, so ``cap.world.step.v1`` takes
``{ticks, action}`` with ``action.values`` a list of one task index per learning agent (each 0 to 2 in the default
setup, bounded by the environment's ``MultiDiscrete`` action space), ``cap.world.reset.v1`` takes ``{seed,
options}`` and ``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware backend,
no native stop and no operator-required limit.

The upstream package imports legacy ``gym`` and ``pybullet`` (recon_arena.py:5-8), which are not installed where the
gate runs, and package code never imports the clone.  The ``fake`` backend is therefore this package's pure Python
``FakeReconArena`` (fake.py), a kinematic stand-in, not the upstream environment; the bridge's upstream path
(``gymnasium.make`` then legacy ``gym.make``) was not run here.  The fidelity contract is F0 because that kinematic
fake is the model as deployed and checked; the gaps say what it does not model and that upstream is a PyBullet
rigid-body simulation.

Every constant and rule in ``facts`` cites a line of the clone at the pinned commit
85a4373f3ebee66b12c88a0bdd5e4e96f9606e5a.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

RECON = "gym_marl_reconnaissance/envs/recon_arena.py"
REGISTRATION = "gym_marl_reconnaissance/__init__.py"


class ReconArena(GymnasiumDriver):
    device_id = "recon-arena"
    env_id = "recon-arena-v0"
    native = "gym_marl_reconnaissance.envs.recon_arena:ReconArena"
    backends = {"fake": ".fake:FakeReconArena"}
    display_name = "gym-marl-reconnaissance ReconArena (recon-arena-v0)"
    vendor, model = "JacopoPan", "recon-arena-v0"
    tags = ["multi-agent", "reconnaissance", "tello", "robomaster", "pybullet", "reinforcement-learning",
            "simulation", "gymnasium"]
    facts = [
        Fact("The environment is registered with gym as recon-arena-v0, entry point "
             "gym_marl_reconnaissance.envs.recon_arena:ReconArena", source="upstream_code",
             ref=f"{REGISTRATION}:3-5"),
        Fact("The constructor defaults are seed -1, ctrl_freq 5 Hz, pyb_freq 60 Hz, episode_length_sec 30 s, "
             "action_type task_assignment, obs_type global, reward_choice reward_a, adv_type avoidant, "
             "visibility_threshold 8 and a setup of edge 10 m, 0 obstacles, 1 Tello, 1 RoboMaster, 2 adversaries "
             "and 1 neutral agent", source="upstream_code", ref=f"{RECON}:74-87"),
        Fact("A seed of -1 leaves numpy's global generator unseeded; any other seed calls np.random.seed(seed)",
             source="upstream_code", ref=f"{RECON}:122-125"),
        Fact("The constructor derives _PYB_UPDATES_PER_STEP = pyb_freq/ctrl_freq and _PYB_TIMESTEP = 1/pyb_freq "
             "after rejecting a pyb_freq that is not divisible by ctrl_freq or is smaller", source="upstream_code",
             ref=f"{RECON}:130-134"),
        Fact("step raises RuntimeError until reset has been called at least once", source="upstream_code",
             ref=f"{RECON}:274-275"),
        Fact("The simulation gravity is 9.8 m/s2 and the Tello mass is 0.08 kg", source="upstream_code",
             ref=f"{RECON}:136-139"),
        Fact("reset resets the PyBullet simulation, sets gravity, loads the plane and creates the obstacle, Tello, "
             "RoboMaster, adversary and neutral teams", source="upstream_code",
             ref=f"{RECON}:210-221"),
        Fact("The action space is MultiDiscrete with one entry per learning agent (Tello plus RoboMaster): the "
             "number of adversaries plus neutrals for task_assignment (3 with the default setup) and 5 for "
             "tracking (stay, forward, backward, left, right)", source="upstream_code", ref=f"{RECON}:353-359"),
        Fact("The global observation space is a Box of 5 values per Tello, RoboMaster, adversary, neutral and "
             "obstacle, with bounds -inf to +inf and dtype float32", source="upstream_code", ref=f"{RECON}:372-376"),
        Fact("The global observation concatenates, for each Tello and RoboMaster, its body id, class and position, "
             "then the same for visible adversaries and neutrals (zeros when not visible), then the obstacles",
             source="upstream_code", ref=f"{RECON}:398-418"),
        Fact("A Tello has class 1 and a RoboMaster class 2 in the state", source="upstream_code",
             ref=f"{RECON}:671-688"),
        Fact("An adversary has class 3 in the state", source="upstream_code", ref=f"{RECON}:692-696"),
        Fact("A neutral agent has class 4 in the state", source="upstream_code", ref=f"{RECON}:749-753"),
        Fact("An obstacle has class 5 in the state", source="upstream_code", ref=f"{RECON}:807-814"),
        Fact("task_assignment forces the number of obstacles to 0 and the visibility threshold to np.inf",
             source="upstream_code", ref=f"{RECON}:152-155"),
        Fact("Without obstacles, an adversary or neutral is visible when it is within visibility_threshold of a "
             "Tello or RoboMaster; with obstacles the line-of-sight ray must strike it as well", source="upstream_code",
             ref=f"{RECON}:699-782"),
        Fact("A task_assignment action computes target_id = val + 1 + obstacles + tt + s1 and sets a velocity of "
             "2 m/s toward the target, multiplied by 1.5 for a RoboMaster", source="upstream_code",
             ref=f"{RECON}:518-542"),
        Fact("A tracking action is 0 stay, 1 forward, 2 backward, 3 left, 4 right, and the move vector is scaled "
             "by 1.2", source="upstream_code", ref=f"{RECON}:549-565"),
        Fact("An avoidant adversary flees a Tello or RoboMaster closer than 3 m at 2.25 times its own speed; "
             "otherwise it patrols along [1, -1] and flips its direction with probability 0.05",
             source="upstream_code", ref=f"{RECON}:609-621"),
        Fact("Adversary and neutral patrol speeds are drawn uniformly from 0.5 to 1.5", source="upstream_code",
             ref=f"{RECON}:223-226"),
        Fact("reward_a is +1 for every adversary within 1.5 of any Tello or RoboMaster", source="upstream_code",
             ref=f"{RECON}:450-456"),
        Fact("reward_b sums 1/(the distance to the closest Tello or RoboMaster + 0.01) over the adversaries",
             source="upstream_code", ref=f"{RECON}:467-472"),
        Fact("reward_c sums 1/(d^2+0.01) over the adversaries and 0.25/(d^2+0.01) for every Tello and RoboMaster "
             "over the closest adversary", source="upstream_code", ref=f"{RECON}:485-502"),
        Fact("The episode ends when (ctrl_step_counter + 1) / ctrl_freq >= episode_length_sec",
             source="upstream_code", ref=f"{RECON}:657-661"),
        Fact("step returns the observation, reward, done and an empty info dict, the legacy gym four-tuple",
             source="upstream_code", ref=f"{RECON}:305-313"),
        Fact("A Tello starts at z=1.5 and a RoboMaster at z=0.5, each with x and y uniform in [0, edge/3]",
             source="upstream_code", ref=f"{RECON}:847-876"),
        Fact("An adversary or neutral starts at z=0.5 with x and y uniform in [2*edge/3, edge]", source="upstream_code",
             ref=f"{RECON}:893-922"),
        Fact("The render frame is 640 by 480", source="upstream_code", ref=f"{RECON}:159-160"),
        Fact("close disconnects from PyBullet", source="upstream_code", ref=f"{RECON}:334-342"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: Fidelity of the model as deployed on the checked backend (spec 05-fidelity).  The fake advances positions
    #: kinematically, so the claim is F0; upstream is a PyBullet rigid-body simulation and was not run here.
    fidelity = {
        "engine": "gym_marl_reconnaissance:recon-arena-v0 (fake backend: kinematic stand-in for the PyBullet "
                  "simulation)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) re-seeds the fake's generator and cap.world.seed.v1 seeds the next reset, after "
                     "which the fake is deterministic; upstream seeds numpy's global generator in the constructor "
                     "(recon_arena.py:122-125), so one seed gives different trajectories on the fake and upstream",
        },
        "timestep_ms": 200.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic fake: positions are advanced directly at the speeds the upstream code sets, so there is no "
            "PyBullet rigid-body dynamics, no contacts, friction, gravity or Tello lift force and no URDF collision "
            "model",
            "the fake reproduces the constructor's default task_assignment setup only (edge 10 m, 0 obstacles, "
            "1 Tello, 1 RoboMaster, 2 adversaries, 1 neutral); a different setup, action_type, obs_type, "
            "reward_choice or adv_type changes the upstream spaces and is not implemented by the fake",
            "no ray-cast line of sight: the fake's visibility is the distance threshold only, and task_assignment "
            "sets that threshold to np.inf anyway",
            "no rendering, GUI or recording: the fake implements no render() and produces no frame",
            "the fake draws from Python's random.Random while upstream draws from numpy's global generator, so one "
            "seed does not give the same trajectory on the two; it returns plain Python lists of floats where "
            "upstream returns a float32 numpy array, and its state entries carry an identity quaternion and zero "
            "velocities",
            "the PyBullet physics substeps (pyb_freq/ctrl_freq = 12 updates of 1/60 s per control step) are not "
            "simulated: one bridge tick advances one control period of timestep_ms",
            "the fake was not compared with a run of the upstream environment; gym and pybullet were not installed "
            "where the gate ran",
            "snapshot and restore are not offered: the fake and ReconArena expose no get_state/set_state",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
