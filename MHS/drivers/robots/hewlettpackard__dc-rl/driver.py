"""OpenMHS driver for gh.hewlettpackard/dc-rl: the SustainDC data-center benchmark (a Gymnasium family driver).

SustainDC is a set of Python environments for benchmarking multi-agent reinforcement learning in data centers
(README.md:25).  The top-level ``sustaindc_env:SustainDC`` is a ``gymnasium.Env`` (sustaindc_env.py:90) that
composes three agent environments: load shifting, data center and battery (sustaindc_env.py:148-153).  The default
configuration runs ``agent_ls``, ``agent_dc`` and ``agent_bat`` (sustaindc_env.py:40), each with a ``Discrete(3)``
action space.  The Gymnasium bridge derives the contract from the environment the selected backend builds.  The
fake's ``cap.world.step.v1`` takes ``{ticks, action}`` with ``action`` a dict of the three agent keys;
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.  The device is
simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The upstream environment is not registered with ``gymnasium.make`` and its constructor takes an ``EnvConfig``
mapping (sustaindc_env.py:91-99); it also needs gymnasium, numpy, pandas, torch and the workload, weather and
carbon-intensity data files.  The ``fake`` backend is this package's pure Python stand-in (``fake.py``), which
models the three default agent keys, Dict spaces, observation sizes and bounds with placeholder transitions.  The
``sim`` backend's factory builds the real ``SustainDC`` with ``month`` 6 (harl/configs/envs_cfgs/sustaindc.yaml:14)
and ``agents`` ``['agent_dc']``.  A step that omits ``agent_dc`` calls ``BaseHVACAgent.act``
(sustaindc_env.py:637-641), and that class defines ``do_nothing_action`` only (utils/base_agents.py:29-58).  With
that one agent configured, ``step`` puts one reward and one flag pair in the returned dicts
(sustaindc_env.py:692-694); the wrapper returns those values unchanged.  The fake was never compared with the
upstream environment.  This module does not import the clone; the orchestrator's ``--backend sim`` run does.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
an F0 analytic simulator with no physical counterpart.  Every constant and rule cites a line of the clone at the
pinned commit (a92b4755aca560e34a98d14028dda629eb968482).  This package is model-authored and unreviewed.  The
check run here uses the fake backend.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "sustaindc_env.py"
LS = "envs/carbon_ls.py"
DC = "utils/make_envs_pyenv.py"
BAT = "envs/bat_env_fwd_view.py"
# The one configured agent on the sim backend.  Omitting it makes step call BaseHVACAgent.act
# (sustaindc_env.py:637-641); BaseHVACAgent defines do_nothing_action only (utils/base_agents.py:29-58).
_SIM_AGENT = "agent_dc"


class _OneAgentSustainDC:
    """Real ``SustainDC`` built with ``agents=['agent_dc']``, returning that agent's step values.

    ``SustainDC`` stores ``observation_space`` and ``action_space`` as lists with one sub-space per configured
    agent (sustaindc_env.py:164-190).  With only ``agent_dc`` those lists hold the data-center ``Discrete`` and
    ``Box``.  ``step`` returns per-agent dicts (sustaindc_env.py:533-621); the configured agent is the one entry
    written at sustaindc_env.py:692-694.  This wrapper returns that reward and those flags unchanged, and places
    the bridge's ``Discrete`` index under the ``agent_dc`` key (sustaindc_env.py:637-638).  ``reset`` takes no
    arguments and returns the states dict only (sustaindc_env.py:436, :531); ``seed`` seeds numpy, Python's
    random and torch (sustaindc_env.py:241-251).
    """

    def __init__(self, env):
        self._env = env
        # The lists have one element: the data-center Discrete and Box (sustaindc_env.py:181-183).
        self.action_space = env.action_space[0]
        self.observation_space = env.observation_space[0]

    def reset(self, seed=None, options=None):
        # Upstream reset() takes no seed (sustaindc_env.py:436).  seed() is the seeding path (sustaindc_env.py:241).
        if seed is not None:
            self._env.seed(int(seed))
        state = self._env.reset()
        return state[_SIM_AGENT], {}

    def step(self, action):
        # The integer is the Discrete index the data-center environment maps (utils/make_envs_pyenv.py:127-132).
        observation, reward, terminated, truncated, info = self._env.step({_SIM_AGENT: action})
        return (
            observation[_SIM_AGENT],
            reward[_SIM_AGENT],
            terminated[_SIM_AGENT],
            truncated[_SIM_AGENT],
            info,
        )

    def seed(self, seed=None):
        return self._env.seed(seed)

    def close(self):
        # SustainDC.close calls self.env.close() (sustaindc_env.py:739-743).  The bridge swallows close errors.
        return self._env.close()


def _build_sim_sustaindc(**_options):
    """Build ``sustaindc_env:SustainDC`` for the sim backend.

    The constructor evaluates ``self.month + 1`` (sustaindc_env.py:148-152).  The training configuration sets
    ``month: 6`` (harl/configs/envs_cfgs/sustaindc.yaml:14).  ``EnvConfig`` keeps every other default
    (sustaindc_env.py:38-87), including the New York data files, and replaces ``agents`` with the one agent
    whose step path has a method (sustaindc_env.py:174-190).  The import is inside this function: the fake
    backend runs where the clone is not installed.
    """
    from sustaindc_env import SustainDC

    return _OneAgentSustainDC(SustainDC({"month": 6, "agents": [_SIM_AGENT]}))


class SustainDC(GymnasiumDriver):
    device_id = "sustaindc"
    # No gymnasium registration exists upstream: SustainDC is constructed from an EnvConfig mapping.  The fake
    # backend supplies its own environment.  The sim backend's factory builds the class.
    env_id = None
    native = "sustaindc_env:SustainDC"
    backends = {"fake": ".fake:FakeSustainDC", "sim": _build_sim_sustaindc}
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
        Fact("EnvConfig copies DEFAULT_CONFIG and overrides the keys of the mapping passed to the constructor",
             source="upstream_code", ref=f"{ENV}:82-87"),
        Fact("When the config has no worker_index, the constructor reads month and passes month + 1 to "
             "make_dc_pyeplus_env", source="upstream_code", ref=f"{ENV}:126-152"),
        Fact("The training configuration sets month to 6", source="upstream_code",
             ref="harl/configs/envs_cfgs/sustaindc.yaml:14"),
        Fact("observation_space and action_space are lists, one sub-space for each configured agent, and a missing "
             "agent is given a base controller", source="upstream_code", ref=f"{ENV}:164-190"),
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
        Fact("When agent_dc is not configured, _perform_actions calls base_agents['agent_dc'].act",
             source="upstream_code", ref=f"{ENV}:637-641"),
        Fact("BaseHVACAgent defines do_nothing_action and has no act method", source="upstream_code",
             ref="utils/base_agents.py:29-58"),
        Fact("The reward, terminated and truncated dicts receive one entry per configured agent",
             source="upstream_code", ref=f"{ENV}:686-699"),
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
            "the sim backend builds SustainDC with month 6 (harl/configs/envs_cfgs/sustaindc.yaml:14) and agents "
            "['agent_dc'] (sustaindc_env.py:174-184): a step that omits agent_dc calls BaseHVACAgent.act "
            "(sustaindc_env.py:637-641) and BaseHVACAgent defines do_nothing_action only "
            "(utils/base_agents.py:29-58); the wrapper returns reward['agent_dc'], terminated['agent_dc'] and "
            "truncated['agent_dc'] (sustaindc_env.py:692-694) and places the Discrete index under the agent_dc key "
            "(sustaindc_env.py:637-638); the fake still serves agent_ls, agent_dc and agent_bat",
        ],
    }
