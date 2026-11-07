"""OpenMHS driver for gh.bark-simulator/bark-ml: the ``highway-v0`` continuous highway environment.

The upstream package registers eight Gym environments (gym.py:154-186).  This package serves the first card entry
symbol, ``bark_ml.environments.gym:ContinuousHighwayGym`` (gym.py:25-36), registered as ``highway-v0``
(gym.py:155-157).  The other registrations (``highway-v1``, ``merging-v0``, ``merging-medium-v0``, ``merging-v1``,
``intersection-v0``, ``intersection-v1`` and ``singlelane-v0``, gym.py:159-185) are separate environments with their
own action spaces and blueprints and are not covered here.  A ``GymnasiumDriver`` is configuration only: ``env_id``
names the environment and the bridge derives ``cap.world.step.v1``, ``cap.world.reset.v1`` and
``cap.world.seed.v1`` from the environment's spaces.

The action space comes from ``BehaviorContinuousML``: two floats, acceleration and steering rate, bounded by
``[-5.0, -0.2]`` and ``[4.0, 0.2]`` (cont_behavior.py:29-43).  The observation comes from ``NearestObserver``:
22 values, six ego values and four per nearest agent (nearest_observer.hpp:66-82).  The environment is simulated
(R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The gate never installs or imports the upstream package (it needs the compiled ``bark-simulator`` extension, gym
and a display).  The ``fake`` backend is this package's pure Python kinematic stand-in (fake.py).  A backend name
that ``backends`` does not list (``sim``) is served by ``gym.make(env_id)`` (GymnasiumDriver.open_native); that path
needs bark-ml installed, the environment registration module imported and a working BARK build, and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every constant and rule cites a line of the clone at the pinned commit (ea2ee58be406e71c5e95c80c0ffbe56c03d6ec60).
This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

GYM = "bark_ml/environments/gym.py"
HIGHWAY = "bark_ml/environments/blueprints/highway/highway.py"
BEHAVIOR = "bark_ml/behaviors/cont_behavior.py"
RUNTIME = "bark_ml/environments/single_agent_runtime.py"
OBSERVER = "bark_ml/observers/nearest_observer.hpp"
EVALUATOR = "bark_ml/evaluators/general_evaluator.py"
README = "Readme.md"


class BarkHighway(GymnasiumDriver):
    device_id = "bark-highway"
    env_id = "highway-v0"
    native = "bark_ml.environments.gym:ContinuousHighwayGym"
    backends = {"fake": ".fake:FakeContinuousHighwayGym"}
    action_space_ref = f"{BEHAVIOR}:29-36"
    display_name = "BARK-ML highway-v0 (continuous highway driving)"
    vendor, model = "BARK Simulator", "highway-v0"
    mode = "simulated"
    risk = "R0"
    tags = ["autonomous-driving", "highway", "reinforcement-learning", "simulation", "gymnasium", "bark-ml"]
    facts = [
        Fact("highway-v0 is registered with the gym entry point bark_ml.environments.gym:ContinuousHighwayGym",
             source="upstream_code", ref=f"{GYM}:155-157"),
        Fact("ContinuousHighwayGym builds the runtime with render=True", source="upstream_code",
             ref=f"{GYM}:35-36"),
        Fact("SingleAgentRuntime.reset and step call render when the runtime was built with render=True",
             source="upstream_code", ref=f"{RUNTIME}:58-89"),
        Fact("The continuous highway behavior model takes the steering rate and the acceleration as its action",
             source="upstream_code", ref=f"{GYM}:25-29"),
        Fact("The continuous action space is BoundedContinuous(2) over acceleration and steering rate, with the "
             "default lower bound [-5.0, -0.2] and upper bound [4.0, 0.2]", source="upstream_code",
             ref=f"{BEHAVIOR}:29-43"),
        Fact("The highway blueprint uses a 0.2 s simulation step", source="upstream_code", ref=f"{HIGHWAY}:103-113"),
        Fact("The highway blueprint builds four lane corridors, marks lane 2 as the controlled ego lane, places the "
             "ego agent between s 40 and 80 and other agents between s 0 and 250", source="upstream_code",
             ref=f"{HIGHWAY}:65-85"),
        Fact("The highway scenario is a curved four-lane road whose vehicles are controlled by the intelligent "
             "driver model (IDM)", source="vendor_doc", ref=f"{README}:30"),
        Fact("The nearest observer defaults to four nearest agents and concatenates six ego values plus four values "
             "per agent, 22 values in total", source="upstream_code", ref=f"{OBSERVER}:66-82"),
        Fact("The ego block is normalized s, d, theta, longitudinal velocity and lateral velocity, followed by the "
             "raw lane-corridor index", source="upstream_code", ref=f"{OBSERVER}:100-109"),
        Fact("The observer declares its observation space as a Box over observation_len_ values with low 0 and "
             "high 1", source="upstream_code", ref=f"{OBSERVER}:170-176"),
        Fact("The default step-count evaluator terminates an episode after more than 220 steps",
             source="upstream_code", ref=f"{EVALUATOR}:88-91"),
        Fact("SingleAgentRuntime.reset takes only a scenario and returns the observer's observation",
             source="upstream_code", ref=f"{RUNTIME}:47-64"),
        Fact("SingleAgentRuntime.step advances the world by its fixed step time and returns observation, reward, "
             "done and info", source="upstream_code", ref=f"{RUNTIME}:66-91"),
        Fact("The continuous highway blueprint's scenario generator uses random_seed 0 by default",
             source="upstream_code", ref=f"{HIGHWAY}:119-125"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the last observation stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: determinism and timestep fields; they are written out here so the whole contract reads in one place.
    fidelity = {
        "engine": "bark-ml:highway-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "the upstream environment has no seed parameter: SingleAgentRuntime.reset takes a scenario "
                     "instead, and the scenario generator is configured with random_seed 0; the fake always starts "
                     "the same fixed episode and ignores the bridge's seed, so cap.world.seed.v1 is accepted but "
                     "does not change a trajectory",
        },
        "timestep_ms": 200.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a kinematic stand-in: it integrates acceleration and steering rate on a straight lane and "
            "does not model BARK's round road, lane geometry, IDM/MOBIL traffic, collisions, the goal polygon or "
            "the reward-shaping evaluator",
            "the observation uses the 22-value NearestObserver layout, but the four other-agent blocks are static "
            "placeholders and the raw lane index is put in the sixth element as the upstream observer does, "
            "although the declared Box is [0, 1]",
            "the fake starts the ego at rest, ends an episode after the upstream default of 221 steps or after a "
            "placeholder lane departure, and ignores reset seeds and reset options",
            "no rendering: the upstream ContinuousHighwayGym always constructs the viewer and renders on reset and "
            "step, so its real backend needs a display",
            "the sim backend was not run: bark-ml needs the compiled bark-simulator package, gym, the environment "
            "registration import and a display; this package was checked on its fake backend only",
            "snapshot and restore are not offered: SingleAgentRuntime exposes no get_state/set_state",
        ],
    }
