"""OpenMHS driver for gh.hewlettpackard/dc-rl: the SustainDC data-center benchmark (a Gymnasium family driver).

SustainDC is a set of Python environments for benchmarking multi-agent reinforcement learning in data centers
(README.md:25).  The top-level ``sustaindc_env:SustainDC`` is a ``gymnasium.Env`` (sustaindc_env.py:90) that
composes three agent environments: load shifting, data center and battery (sustaindc_env.py:148-153).  The default
configuration runs ``agent_ls``, ``agent_dc`` and ``agent_bat`` (sustaindc_env.py:40), each with a ``Discrete(3)``
action space.  The Gymnasium bridge derives the contract from the environment's spaces: ``cap.world.step.v1`` takes
``{ticks, action}`` with ``action`` a dict of the three agent keys, ``cap.world.reset.v1`` takes ``{seed, options}``
and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to
a machine and no operator-required limit.

The upstream environment is not registered with ``gymnasium.make`` and its constructor takes an ``EnvConfig``
mapping (sustaindc_env.py:91-99); it also needs gymnasium, numpy, pandas, torch and the workload, weather and
carbon-intensity data files.  The only backend is therefore the package's own pure Python fake (``fake.py``), which
models the upstream agent keys, Dict spaces, observation sizes and bounds with placeholder transitions.  The fake
was never compared with the upstream environment, and the card's ``mock_strategy.preferred`` ``upstream-sim`` path
was not run.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
an F0 analytic simulator with no physical counterpart.  Every constant and rule cites a line of the clone at the
pinned commit (a92b4755aca560e34a98d14028dda629eb968482).  This package is model-authored and unreviewed: it is
checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "sustaindc_env.py"
LS = "envs/carbon_ls.py"
DC = "utils/make_envs_pyenv.py"
BAT = "envs/bat_env_fwd_view.py"


class SustainDC(GymnasiumDriver):
    device_id = "sustaindc"
    # No gymnasium registration exists upstream: SustainDC is constructed from an EnvConfig mapping, so the
    # package's fake supplies the environment object on the fake backend.
    env_id = None
    native = "sustaindc_env:SustainDC"
    backends = {"fake": ".fake:FakeSustainDC"}
    display_name = "SustainDC data-center control benchmark"
    vendor, model = "Hewlett Packard Enterprise", "SustainDC"
    tags = ["sustaindc", "datacenter", "multi-agent", "energy", "carbon", "battery", "reinforcement-learning",
            "simulation", "gymnasium"]
    facts = [
        Fact("SustainDC subclasses gymnasium.Env", source="upstream_code", ref=f"{ENV}:90"),
        Fact("SustainDC is constructed from an EnvConfig mapping, not through a gymnasium.make registration",
             source="upstream_code", ref=f"{ENV}:91-99"),
        Fact("The default EnvConfig runs three agents: agent_ls, agent_dc and agent_bat", source="upstream_code",
             ref=f"{ENV}:40"),
        Fact("SustainDC builds the load-shifting, data-center and battery environments with make_ls_env, "
             "make_dc_pyeplus_env and make_bat_fwd_env", source="upstream_code", ref=f"{ENV}:148-153"),
        Fact("The load-shifting action space is Discrete(3): 0 defers all shiftable tasks, 1 does nothing and 2 "
             "processes all deferred tasks", source="upstream_code", ref=f"{LS}:36-40"),
        Fact("The data-center action space is Discrete(3): a -1, 0 or +1 delta to the cooling setpoint",
             source="upstream_code", ref=f"{DC}:127-132"),
        Fact("The battery action space is Discrete(3): 0 charge, 1 discharge and 2 idle", source="upstream_code",
             ref=f"{BAT}:27-28"),
        Fact("The load-shifting observation is a Box of 26 elements from -2 to 2", source="upstream_code",
             ref=f"{LS}:45"),
        Fact("The data-center observation is a Box of 14 elements from -1 to 1", source="upstream_code",
             ref=f"{DC}:114-116"),
        Fact("The battery observation is a Box of 13 elements from -1 to 1", source="upstream_code",
             ref=f"{BAT}:23-24"),
        Fact("reset returns one state per configured agent in a dict", source="upstream_code", ref=f"{ENV}:499-531"),
        Fact("step takes an action dict and returns observation, reward, terminated and truncated dicts plus an "
             "info dict", source="upstream_code", ref=f"{ENV}:533-621"),
        Fact("_perform_actions reads the agent_ls, agent_dc and agent_bat keys of the action dict",
             source="upstream_code", ref=f"{ENV}:624-653"),
        Fact("seed() seeds numpy, Python's random generator and torch", source="upstream_code", ref=f"{ENV}:241-249"),
        Fact("The simulation advances in quarter-hour steps: four timesteps per hour", source="upstream_code",
             ref=f"{DC}:194"),
        Fact("At the end of an episode every agent is marked truncated and terminated stays false",
             source="upstream_code", ref=f"{ENV}:713-718"),
        Fact("The three individual rewards are produced by the ls, dc and bat reward methods", source="upstream_code",
             ref=f"{ENV}:721-739"),
        Fact("The README describes SustainDC as a set of environments for benchmarking multi-agent reinforcement "
             "learning in data centers", source="vendor_doc", ref="README.md:25"),
        Fact("The README says the environments are wrapped in the Gymnasium Env class", source="vendor_doc",
             ref="README.md:41"),
        Fact("The README says three interconnected environments simulate data-center operations", source="vendor_doc",
             ref="README.md:113"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "sustaindc:SustainDC",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) fixes the fake's initial agent states and its transitions are deterministic, so "
                     "one seed and action sequence repeat a trajectory; upstream reset() takes no seed and seeds "
                     "numpy, Python and torch through seed(), so a seed does not reproduce an upstream trajectory",
        },
        # utils/make_envs_pyenv.py:194: four timesteps per hour, so one tick is 15 minutes.
        "timestep_ms": 900000.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "analytic F0 model: the workload, carbon-intensity, weather and battery transitions are placeholder "
            "agent-state updates, not the upstream managers or the data-center thermal, energy and battery models",
            "the bridge serves cap.world.step.v1 as one scalar reward (the sum of three placeholder individual "
            "rewards) and one terminated/truncated flag, while upstream SustainDC returns per-agent reward, "
            "termination and truncation dicts",
            "the fake accepts reset(seed, options) and returns a Gymnasium (observation, info) pair; upstream "
            "reset() takes no arguments and returns only the per-agent state dict, and upstream step() expects a "
            "dict keyed by agent",
            "the fake was never compared with the upstream environment: upstream needs gymnasium, numpy, pandas, "
            "torch and the workload, weather and carbon-intensity data files, which were not installed or run",
            "the fake models no data-center physics and offers no rendering, dashboard, snapshot or restore",
            "wall-clock time is not paced: realtime_factor 0 and simulated time advances 15 minutes per tick only",
        ],
    }
