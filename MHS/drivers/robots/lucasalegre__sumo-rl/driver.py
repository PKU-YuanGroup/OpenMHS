"""OpenMHS driver for gh.lucasalegre/sumo-rl: the SUMO traffic-signal environment (a Gymnasium family driver).

A ``GymnasiumDriver`` is configuration only: ``env_id`` names the registered environment (``sumo-rl-v0``) and the
bridge derives the contract from the environment's spaces.  This package serves the single-agent Gymnasium API
(``kwargs={"single_agent": True}`` at registration) on the single-intersection network used by the upstream gym
test: the action space is ``Discrete(num_green_phases)`` and the observation space is
``Box(0, 1, shape=(num_green_phases + 1 + 2 * len(lanes),))``.  ``cap.world.step.v1`` takes ``{ticks, action}``
with ``action.index`` bounded by the action space, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): it has no hardware backend and no operator-required
limit.

The gate does not install sumo-rl, SUMO, sumolib, traci or numpy (the upstream import needs ``SUMO_HOME`` and the
SUMO tools, ``sumo_rl/environment/env.py:8-12``), and package code never imports the clone.  The ``fake`` backend is
therefore a pure-Python stand-in for ``SumoEnvironment`` (see fake.py).  A backend name that ``backends`` does not
list (``sim``) is served by ``gymnasium.make(env_id, **env_kwargs)`` through ``GymnasiumDriver.open_native``; that
path needs the upstream package and SUMO and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
every member of ``device.schema.json`` that applies to a simulator without a physical counterpart.  Every constant
and rule cites a line of the clone at the pinned commit (86f0fc41401eeca724b2e8878f5020dc6d70c9b4).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "sumo_rl/environment/env.py"
SIGNAL = "sumo_rl/environment/traffic_signal.py"
OBS = "sumo_rl/environment/observations.py"
REGISTER = "sumo_rl/environment/__init__.py"
NET = "sumo_rl/nets/single-intersection/single-intersection.net.xml"
TEST = "tests/gym_test.py"


class SumoRL(GymnasiumDriver):
    device_id = "sumo-rl"
    env_id = "sumo-rl-v0"
    #: The configuration of the upstream gym test (tests/gym_test.py:8-14) and the single-intersection network;
    #: the paths are relative to the repository root, where the driver package and the clone live.  The fake
    #: backend ignores them; the sim backend was not run (see the fidelity gaps).
    env_kwargs = {
        "net_file": "robots/lucasalegre/sumo-rl/sumo_rl/nets/single-intersection/single-intersection.net.xml",
        "route_file": "robots/lucasalegre/sumo-rl/sumo_rl/nets/single-intersection/single-intersection.rou.xml",
        "num_seconds": 100,
    }
    seed = 0
    native = "sumo_rl.environment.env:SumoEnvironment"
    backends = {"fake": ".fake:FakeSumoEnvironment"}
    display_name = "SUMO-RL traffic signal control (single intersection, simulated)"
    vendor, model = "Lucas Alegre", "sumo-rl-v0"
    tags = ["sumo-rl", "sumo", "traffic-signal-control", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("sumo-rl-v0 is registered with entry point sumo_rl.environment.env:SumoEnvironment and kwargs "
             "single_agent=True", source="upstream_code", ref=f"{REGISTER}:6-10"),
        Fact("SumoEnvironment is a gymnasium.Env for traffic signal control with the SUMO simulator",
             source="upstream_code", ref=f"{ENV}:51-56"),
        Fact("The environment module raises ImportError when SUMO_HOME is not set", source="upstream_code",
             ref=f"{ENV}:8-12"),
        Fact("The constructor requires net_file and route_file", source="upstream_code", ref=f"{ENV}:96-97"),
        Fact("num_seconds, the simulated seconds of one episode, defaults to 20000", source="upstream_code",
             ref=f"{ENV}:102"),
        Fact("delta_time, the simulated seconds between actions, defaults to 5 and yellow_time defaults to 2",
             source="upstream_code", ref=f"{ENV}:106-107"),
        Fact("min_green defaults to 5 s and max_green defaults to 50 s", source="upstream_code",
             ref=f"{ENV}:108-109"),
        Fact("sumo_seed defaults to 'random', so a run without a reset seed is not reproducible",
             source="upstream_code", ref=f"{ENV}:117"),
        Fact("sim_max_time is begin_time plus num_seconds", source="upstream_code", ref=f"{ENV}:142"),
        Fact("reset closes the previous simulation, increments the episode, masks a supplied seed to 31 bits and "
             "starts SUMO again", source="upstream_code", ref=f"{ENV}:263-271"),
        Fact("For single_agent the reset returns (observation, info)", source="upstream_code", ref=f"{ENV}:280-281"),
        Fact("For single_agent step returns (observation, reward, terminated, truncated, info); terminated is "
             "always False and truncated is dones['__all__']", source="upstream_code", ref=f"{ENV}:305-313"),
        Fact("The episode truncates when sim_step is at least sim_max_time", source="upstream_code",
             ref=f"{ENV}:341-344"),
        Fact("close stops the SUMO simulation and sets self.sumo to None", source="upstream_code",
             ref=f"{ENV}:459-472"),
        Fact("sumo_seed is passed to SUMO as --seed unless it is 'random', which passes --random",
             source="upstream_code", ref=f"{ENV}:228-231"),
        Fact("The action space is Discrete(num_green_phases), one action per green phase", source="upstream_code",
             ref=f"{SIGNAL}:118"),
        Fact("The default reward is the change in cumulative vehicle delay, with waiting times divided by 100",
             source="upstream_code", ref=f"{SIGNAL}:232-236"),
        Fact("The default observation concatenates the one-hot green phase, a min-green flag, lane densities and "
             "lane queues", source="upstream_code", ref=f"{OBS}:38-43"),
        Fact("The observation space is Box from 0 to 1 with length num_green_phases + 1 + 2 * len(lanes)",
             source="upstream_code", ref=f"{OBS}:45-50"),
        Fact("The upstream gym test creates sumo-rl-v0 with the single-intersection network and num_seconds=100",
             source="upstream_code", ref=f"{TEST}:8-14"),
        Fact("The single-intersection network has two incoming lanes from the north and two from the west",
             source="upstream_code", ref=f"{NET}:41-55"),
        Fact("The single-intersection network declares two green phases and two yellow phases",
             source="upstream_code", ref=f"{NET}:58-63"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "sumo-rl:SUMO traffic signal control",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "A reset seed is masked to 31 bits and passed to SUMO as --seed (env.py:228-231, :269-270); "
                     "cap.world.seed.v1 supplies the seed of the next reset.  The upstream default sumo_seed is "
                     "'random' (env.py:117), so a run without a seed is not reproducible.  The fake reseeds its "
                     "initial lane loads with Python's random.Random(seed); the SUMO backend was not run, so "
                     "agreement between the two was not measured.",
        },
        "timestep_ms": 5000.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "F0: the fake is an analytic/kinematic stand-in and models no vehicle dynamics, car-following, lane "
            "changing, routing, traffic-signal timing or TraCI interaction; the SUMO engine itself models traffic "
            "dynamics but was not run for this package (SUMO_HOME, sumolib and traci are external dependencies)",
            "no wall-clock pacing: realtime_factor 0, and each cap.world.step.v1 tick advances simulated time by "
            "timestep_ms (delta_time 5 s, env.py:106 and :143) only",
            "no physical intersection or traffic light is modelled, and the model was never validated against "
            "SUMO or a real intersection",
            "the fake backend is a pure-Python stand-in that returns Python floats (upstream returns float32 "
            "numpy arrays from TraCI), models one traffic signal with two green phases and four controlled lanes "
            "(the single-intersection network of tests/gym_test.py:8-14), and was not compared with the upstream "
            "environment; SUMO and sumo-rl were not installed where the gate ran",
            "snapshot and restore are not offered: SumoEnvironment exposes no get_state/set_state, and a reset "
            "closes and restarts the SUMO simulation (env.py:263-271)",
            "the sim backend was not run: it needs SUMO_HOME and the upstream package installed, and "
            "gym.make('sumo-rl-v0', **env_kwargs) with the configured net_file and route_file paths (relative to "
            "the repository root)",
        ],
    }
