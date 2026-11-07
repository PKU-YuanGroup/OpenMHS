"""OpenMHS driver for gh.chemgymrl/chemgymrl: the GenWurtzExtract-v2 chemistry bench (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}``; the action is
``{index}`` because the bench's action space is ``gym.spaces.Discrete``, ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required limit.

The gate never imports the upstream package or the clone, so the ``fake`` backend is the package's own stand-in for
``chemistrylab.benches.extract_bench:GeneralWurtzExtract_v2`` (see fake.py).  A backend name that ``backends`` does
not list (``sim``) is served by ``gymnasium.make("GenWurtzExtract-v2")`` (GymnasiumDriver.open_native); that path
needs the upstream package installed and was not run here.

The ``fidelity`` attribute describes the model as deployed (spec 05-fidelity FID-002).  Every constant and rule
below cites a line of the clone at the pinned commit (ab8227b6b33f13617b7e551bdf6b894df7eec68d).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

INIT = "chemistrylab/__init__.py"
BENCH = "chemistrylab/benches/general_bench.py"
EXTRACT = "chemistrylab/benches/extract_bench.py"
CHARACTERIZATION = "chemistrylab/benches/characterization_bench.py"
REACTION = "chemistrylab/reactions/available_reactions/chloro_wurtz.json"


class GenWurtzExtract(GymnasiumDriver):
    device_id = "genwurtz-extract"
    env_id = "GenWurtzExtract-v2"
    native = "chemistrylab.benches.extract_bench:GeneralWurtzExtract_v2"
    backends = {"fake": ".fake:FakeGeneralWurtzExtract"}
    display_name = "ChemGymRL GenWurtzExtract-v2 extraction bench"
    vendor, model = "ChemGymRL", "GenWurtzExtract-v2"
    tags = ["chemistry", "extraction", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("GenWurtzExtract-v2 is registered with entry point "
             "chemistrylab.benches.extract_bench:GeneralWurtzExtract_v2", source="upstream_code",
             ref=f"{INIT}:15-18"),
        Fact("The registration passes only id and entry_point: there is no max_episode_steps wrapper, so the "
             "environment's own max_steps is the only step bound", source="upstream_code", ref=f"{INIT}:15-18"),
        Fact("GenBench defaults max_steps to 50", source="upstream_code", ref=f"{BENCH}:68"),
        Fact("The episode ends when the selected Action is terminal or the step counter reaches max_steps",
             source="upstream_code", ref=f"{BENCH}:213"),
        Fact("GenBench counts n_actions as one action per parameter row of every Action",
             source="upstream_code", ref=f"{BENCH}:85"),
        Fact("GenBench builds a discrete action space as gym.spaces.Discrete(self.n_actions)",
             source="upstream_code", ref=f"{BENCH}:99"),
        Fact("GeneralWurtzExtract_v2 has nine Action entries and its amounts parameters hold five rows each "
             "(np.linspace(0.2, 1, 5).reshape([5, 1])); the last Action holds one row, so the flattened list has "
             "5 + 5 + 5 + 5 + 5 + 5 + 5 + 5 + 1 = 41 discrete actions",
             source="upstream_code", ref=f"{EXTRACT}:166-179"),
        Fact("A discrete action is an index into the flattened (Action, parameter row) list, not into the nine "
             "Action entries", source="upstream_code", ref=f"{BENCH}:229"),
        Fact("The last parameter row of GeneralWurtzExtract_v2 is terminal", source="upstream_code",
             ref=f"{EXTRACT}:178"),
        Fact("The extraction bench's shelf has three working vessels", source="upstream_code", ref=f"{EXTRACT}:165"),
        Fact("GeneralWurtzExtract_v2 observes layers and targets", source="upstream_code", ref=f"{EXTRACT}:186"),
        Fact("CharacterizationBench measures 100 layer values per vessel and a target vector whose length is the "
             "number of targets", source="upstream_code", ref=f"{CHARACTERIZATION}:66-70"),
        Fact("encode_target returns a one-hot vector over the targets", source="upstream_code",
             ref=f"{CHARACTERIZATION}:177-186"),
        Fact("The chloro-wurtz reaction file lists seven products", source="upstream_code", ref=f"{REACTION}:9-16"),
        Fact("GeneralWurtzExtract_v2 loads the chloro-wurtz PRODUCTS as its targets", source="upstream_code",
             ref=f"{EXTRACT}:181"),
        Fact("The observation space is gym.spaces.Box(0, 1, observation_shape, dtype=np.float32)",
             source="upstream_code", ref=f"{BENCH}:90"),
        Fact("reset accepts seed and options, reseeds numpy's global generator and the action space, draws a "
             "target uniformly from targets, and returns (observation, {})", source="upstream_code",
             ref=f"{BENCH}:235-240"),
        Fact("step applies the selected action, advances every working vessel and returns "
             "(state, reward, done, False, {})", source="upstream_code", ref=f"{BENCH}:201-222"),
        Fact("Most actions advance a vessel by dt=0.01 s; the two solvent pours and the final mixing action use "
             "dt=0 and the final Action is terminal", source="upstream_code", ref=f"{EXTRACT}:169-178"),
        Fact("The bench metadata declares rgb_array rendering at 10 frames per second", source="upstream_code",
             ref=f"{EXTRACT}:152-155"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    fidelity_level = "F0"
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: determinism kind and lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "analytic:GenWurtzExtract-v2",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) selects the target and initialises the stand-in's vessels; upstream seeds "
                     "numpy's global generator and the action space, so one seed does not select the same target "
                     "in the fake and upstream, and no trajectory was compared with the upstream environment",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a stand-in, not the upstream chemistry simulator: it does not model vessels, material "
            "amounts, spectra, events or the reward generator, and its layer and target values are placeholders",
            "the environment is event-driven, not a fixed-timestep integrator: each Action carries its own dt "
            "(0.01 s for most actions, 0 for the solvent pours and the final mix), so timestep_ms is declared 0",
            "the action count follows the flattened (Action, parameter row) list and the terminal flag of the last "
            "Action, but the fake does not execute the named events",
            "no physical device is modelled and the model was never validated against one",
            "reset options are accepted and ignored, as the upstream reset does not read them",
            "no rendering, no snapshot or restore (the environment exposes no get_state/set_state), and no "
            "wall-clock pacing",
            "the fake returns the full observation shape (three vessels, each with 100 layer values and a "
            "seven-element target one-hot) but the values are placeholder data",
        ],
    }
