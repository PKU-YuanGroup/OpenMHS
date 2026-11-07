"""OpenMHS driver for gh.hzaskywalker/plasticinelab: the Move-v1 soft-body environment (Gymnasium family).

PlasticineLab registers ten environment names with five variants each, building the id at import time as
``f'{env_name}-v{id+1}'`` (``plb/envs/__init__.py:6-13``); the card names the entry class
``plb.envs.env:PlasticineEnv``.  A GymnasiumDriver serves one concrete environment, so this package serves
``Move-v1``, the environment the repository's own usage example runs (``README.md:6``).  The bridge derives the
``cap.world.*`` contract from the environment object: ``cap.world.step.v1`` takes ``{ticks, action}`` with
``action.values`` bounded by the ``Box(-1, 1, (action_dim,))`` that ``PlasticineEnv`` installs
(``plb/envs/env.py:26``), ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` takes
``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no
operator-required limit.

The gate never imports the clone (the upstream needs Taichi, the legacy ``gym`` package, numpy and a GPU; package
code never imports the clone), so the ``fake`` backend is the package's own pure Python stand-in (fake.py).  A
backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make("Move-v1")`` after the legacy
``gym`` registration (GymnasiumDriver.open_native); that path needs the upstream package installed and was not run
here.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity): an MPM soft-body physics
model stepped through Taichi, a fixed 2 ms environment step made of 40 physics substeps, and the 50-step episode
limit of the registration wrapper.  ``gaps`` say what this package's fake does not model.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and its evidence is ``contract_checked``,
never an MHS-Device level.
"""

from mhs.driver import Fact, GymnasiumDriver

INIT = "plb/envs/__init__.py"
ENV = "plb/envs/env.py"
MOVE = "plb/envs/move.yml"
DEFAULT_CONFIG = "plb/config/default_config.py"
PRIMITIVE = "plb/engine/primitive/primive_base.py"
PRIMITIVES = "plb/engine/primitive/primitives.py"
SIMULATOR = "plb/engine/mpm_simulator.py"
TAICHI_ENV = "plb/engine/taichi_env.py"
LOSS = "plb/engine/losses/loss.py"


class PlasticineLab(GymnasiumDriver):
    device_id = "plasticinelab"
    env_id = "Move-v1"
    native = "plb.envs.env:PlasticineEnv"
    backends = {"fake": ".fake:FakePlasticineEnv"}
    action_space_ref = f"{ENV}:26"
    display_name = "PlasticineLab Move-v1 (soft-body manipulation benchmark)"
    vendor, model = "hzaskywalker", "PlasticineLab Move-v1"
    tags = ["plasticinelab", "soft-body", "mpm", "taichi", "manipulation", "reinforcement-learning",
            "simulation", "gymnasium"]
    facts = [
        Fact("PlasticineEnv subclasses gym.Env, takes cfg_path, version and nn, builds a Taichi environment and "
             "initializes it", source="upstream_code", ref=f"{ENV}:12-18"),
        Fact("The environment id is built at import as f'{env_name}-v{id+1}' for ten names and variants 1 to 5, "
             "registered with entry_point plb.envs.env:PlasticineEnv, kwargs cfg_path and version, and "
             "max_episode_steps 50", source="upstream_code", ref=f"{INIT}:6-13"),
        Fact("The README's usage example runs Move-v1", source="vendor_doc", ref="README.md:6"),
        Fact("The action space is Box(-1, 1, (action_dim,)) and the observation space is Box(-inf, inf, "
             "obs.shape)", source="upstream_code", ref=f"{ENV}:25-26"),
        Fact("__init__ captures the initial state with taichi_env.get_state() and then calls reset()",
             source="upstream_code", ref=f"{ENV}:21-24"),
        Fact("reset() takes no seed or options, restores the initial state captured at construction, clears the "
             "recorded actions and returns _get_obs()", source="upstream_code", ref=f"{ENV}:28-31"),
        Fact("_get_obs concatenates every step_size-th particle's position and velocity with the state of every "
             "primitive", source="upstream_code", ref=f"{ENV}:33-41"),
        Fact("step() advances the Taichi environment, computes the loss, appends the action, and returns "
             "(observation, reward, False, loss_info); the done flag is always False", source="upstream_code",
             ref=f"{ENV}:43-57"),
        Fact("The observation stride is len(x) // n_observed_particles", source="upstream_code", ref=f"{ENV}:40-41"),
        Fact("Move has two Sphere primitives and each declares a 3-dimensional action with scale (0.01, 0.01, "
             "0.01)", source="upstream_code", ref=f"{MOVE}:10-26"),
        Fact("Primitives.action_dim is the sum of the action dims of its primitives", source="upstream_code",
             ref=f"{PRIMITIVES}:274-283"),
        Fact("Primitives.set_action flattens the action and clips every element to the interval [-1, 1]",
             source="upstream_code", ref=f"{PRIMITIVES}:290-294"),
        Fact("A primitive state is a 3-value position plus a 4-value rotation quaternion, returned by get_state",
             source="upstream_code", ref=f"{PRIMITIVE}:130-146"),
        Fact("The default number of observed particles is 200", source="upstream_code",
             ref=f"{DEFAULT_CONFIG}:72"),
        Fact("Move sets the particle count to 10000", source="upstream_code", ref=f"{MOVE}:3"),
        Fact("SIMULATOR.quality defaults to 1", source="upstream_code", ref=f"{DEFAULT_CONFIG}:14"),
        Fact("SIMULATOR.dt is 0.5e-4 / quality seconds and SIMULATOR.substeps is int(2e-3 / dt), so at the "
             "default quality 1 one environment step is 40 physics substeps of 0.05 ms (2 ms)",
             source="upstream_code", ref=f"{SIMULATOR}:22-34"),
        Fact("MPMSimulator.step advances the simulation from the current frame by substeps frames",
             source="upstream_code", ref=f"{SIMULATOR}:365-376"),
        Fact("The reward is the start loss minus the step's incremental loss, returned inside loss_info",
             source="upstream_code", ref=f"{LOSS}:288-298"),
        Fact("Taichi is initialized on the GPU at import", source="upstream_code", ref=f"{TAICHI_ENV}:6"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime refuses step and reset until "
                  "mhs.safety.reset clears the latch, and the last world state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).
    fidelity = {
        "engine": "taichi-mpm:PlasticineLab-Move-v1",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "PlasticineEnv.reset() takes no seed: it restores the state captured at construction, so a "
                     "fresh reset plus the same action sequence repeats on one backend. cap.world.reset.v1 and "
                     "cap.world.seed.v1 accept and echo a seed, but it labels the episode and does not change the "
                     "initial state. The upstream initializes Taichi on the GPU and its MPM scatter accumulates "
                     "floating-point contributions in parallel, so bit-identical replay across devices is not "
                     "claimed; the package claims seeded (labelled) replay, not exact.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the deployed model is an MPM soft-body continuum with gravity, contacts, friction and yield stress "
            "(F1: physics with contacts), but it models no actuator, sensor or noise dynamics, so F2 is not "
            "claimed",
            "the fake backend is a pure-Python stand-in for the interface, not the solver: it holds 200 observed "
            "particle positions and velocities as fixed placeholder data and moves only the two primitive "
            "kinematic states by action * 0.01 per step; it models no soft-body deformation, contact, friction, "
            "gravity, yield stress or rendering",
            "the real Move-v1 observation has 1214 values (200 observed particles x 6 position/velocity values "
            "plus 2 primitives x 7 state values); the fake returns the same 1214-value length but its particle "
            "values are placeholders and its reward is always 0.0 with an empty info object, so the loss and "
            "inverse-IoU measurements are not modelled",
            "the fake implements the registration's 50-step episode limit as truncated=True; PlasticineEnv.step "
            "itself always returns done=False and the legacy gym TimeLimit wrapper is what ends the episode",
            "the physics substep is 0.5e-4 s (0.05 ms) and one environment step is 40 substeps (2 ms); "
            "timestep_ms names the 2 ms environment step that one cap.world.step.v1 tick advances",
            "the fake ignores the reset seed and the reset options, matching the upstream reset() signature; the "
            "seed only labels the episode",
            "the sim backend (gymnasium.make('Move-v1') through the legacy gym registration, with Taichi on the "
            "GPU) was not run: the gate does not install or import the clone",
            "snapshot and restore are not offered: PlasticineEnv exposes no get_state/set_state of its own (the "
            "state lives on its taichi_env attribute)",
            "no rendering is bound: cap.world.render.v1 needs an artifact store that OpenMHS 0.9 does not have",
            "no physical device is modelled and the benchmark was never validated against one",
        ],
    }
