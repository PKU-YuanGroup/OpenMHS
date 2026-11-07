"""OpenMHS driver for gh.farama-foundation/mo-gymnasium: the FishWood environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the whole contract
from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{index}`` bounded by
``Discrete(2)`` (0 go fishing, 1 go collect wood), ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a
machine and no operator-required limit.

The card is a driver pack: the repository holds one environment class per file and the card lists five entry symbols.
This package covers one of them, ``mo_gymnasium.envs.fishwood.fishwood:FishWood``, registered as fishwood-v0
(mo_gymnasium/envs/fishwood/__init__.py:4-7); facts.md names the other four classes as not covered.

MO-Gymnasium returns a reward *vector* (README.md:13), while ``cap.world.step.v1``'s ``reward`` is a single number.
The two objectives of FishWood are one-hot, so the fake returns their sum (0 or 1) as the scalar reward and keeps the
full ``[fish, wood]`` vector in ``info["objectives"]``; the vector itself is not carried by the standard's step output
(the fidelity ``gaps`` and RESULT.json say so).

The gate cannot import MO-Gymnasium (the upstream needs gymnasium, numpy and pygame-ce, pyproject.toml:24-28), so the
``fake`` backend is the package's own pure Python two-state world (fake.py).  A backend name that ``backends`` does not
list (``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); for this repository that call
needs ``mo_gymnasium`` imported so the id is registered, and it was not run here (README.md).

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
every member of ``device.schema.json`` that applies to a simulator without a physical counterpart.  Every constant
and rule cites a line of the clone at the pinned commit (8d280fdc3f517b18090619806843c03f51d775af).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENVFILE = "mo_gymnasium/envs/fishwood/fishwood.py"
REGISTRATION = "mo_gymnasium/envs/fishwood/__init__.py"
UTILS = "mo_gymnasium/utils.py"


class FishWood(GymnasiumDriver):
    device_id = "fishwood"
    env_id = "fishwood-v0"
    native = "mo_gymnasium.envs.fishwood.fishwood:FishWood"
    backends = {"fake": ".fake:FakeFishWood"}
    action_space_ref = f"{ENVFILE}:56"
    display_name = "MO-Gymnasium FishWood (fishwood-v0)"
    vendor, model = "Farama Foundation", "fishwood-v0"
    tags = ["fishwood", "multi-objective", "two-state", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("MO-Gymnasium follows the Gymnasium API but returns vectorized rewards as numpy arrays",
             source="vendor_doc", ref="README.md:13"),
        Fact("fishwood-v0 is registered with the entry point mo_gymnasium.envs.fishwood.fishwood:FishWood and no "
             "max_episode_steps wrapper", source="upstream_code", ref=f"{REGISTRATION}:4-7"),
        Fact("The observation space is Box(low=0, high=1, shape=(1,), dtype=int32) and has two states: 0 fishing and "
             "1 in the woods", source="upstream_code", ref=f"{ENVFILE}:15-18"),
        Fact("The action space is Discrete(2): 0 go fishing and 1 go collect wood", source="upstream_code",
             ref=f"{ENVFILE}:20-23"),
        Fact("The reward is 2-dimensional with one objective per resource", source="upstream_code",
             ref=f"{ENVFILE}:25-28"),
        Fact("The state constants are FISH 0, WOOD 1 and MAX_TS 200", source="upstream_code", ref=f"{ENVFILE}:45-47"),
        Fact("The constructor defaults fishproba to 0.1 and woodproba to 0.9", source="upstream_code",
             ref=f"{ENVFILE}:49"),
        Fact("The action space is spaces.Discrete(2)", source="upstream_code", ref=f"{ENVFILE}:56"),
        Fact("The observation space is spaces.Box(low=0, high=1, shape=(1,), dtype=int32)", source="upstream_code",
             ref=f"{ENVFILE}:58"),
        Fact("The reward space is spaces.Box(low=[0, 0], high=[1.0, 1.0], dtype=float32) and reward_dim is 2",
             source="upstream_code", ref=f"{ENVFILE}:60-61"),
        Fact("The fisherman starts in the woods: _state is WOOD and reset restores that state with timestep 0",
             source="upstream_code", ref=f"{ENVFILE}:63-69"),
        Fact("reset calls super().reset(seed=seed), so the seed arms the environment's np_random generator",
             source="upstream_code", ref=f"{ENVFILE}:65-66"),
        Fact("step draws a Bernoulli reward for the state the fisherman is leaving: woodproba pays the wood "
             "objective and fishproba pays the fish objective", source="upstream_code", ref=f"{ENVFILE}:84-89"),
        Fact("step sets the state to [action] and increments the timestep", source="upstream_code",
             ref=f"{ENVFILE}:91-93"),
        Fact("The episode returns terminated and truncated when the timestep equals MAX_TS", source="upstream_code",
             ref=f"{ENVFILE}:97"),
        Fact("The episode ends after MAX_TS = 200 steps", source="upstream_code", ref=f"{ENVFILE}:33-34"),
        Fact("mo_gymnasium.make disables the gymnasium env checker because it requires the reward to be a scalar",
             source="upstream_code", ref=f"{UTILS}:21-22"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  FishWood is a two-state
    #: analytic environment with direct state transitions, so it is F0; the bridge derives the engine, the
    #: determinism kind and the lockstep clock, and the members below say what the world does and does not model.
    fidelity = {
        "engine": "gymnasium:fishwood-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) arms the fake's random generator and the transition rule is deterministic, so one "
                     "seed and one action sequence repeat a trajectory; the fake draws with Python's "
                     "random.Random while upstream draws from numpy's Generator, so the same seed gives different "
                     "reward sequences on the two",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no dynamics: the model has two states (fishing 0 and in the woods 1) and one tick applies the "
            "action's state and the Bernoulli reward of the state left behind; no forces, contacts or continuous "
            "time are modelled (F0)",
            "no simulation time advances: the environment is turn-based, timestep_ms is 0, one tick is one action "
            "and realtime_factor 0 means no wall-clock pacing",
            "the 2-objective reward vector of MO-Gymnasium (README.md:13) is not carried by cap.world.step.v1, "
            "whose reward is a single number; the fake returns the sum of the one-hot objectives (0 or 1) as the "
            "scalar reward and keeps the full [fish, wood] vector in info.objectives, so the vector is absent from "
            "the step output",
            "the fake draws the Bernoulli reward with Python's random.Random instead of numpy's np_random and was "
            "never compared with an upstream run (MO-Gymnasium needs gymnasium, numpy and pygame-ce, which the gate "
            "does not have)",
            "no rendering, no pygame assets, no snapshot/restore (the class exposes no get_state/set_state) and no "
            "physical device is modelled; nothing was validated against one",
        ],
    }
