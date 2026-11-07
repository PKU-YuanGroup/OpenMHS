"""OpenMHS driver for gh.semitable/robotic-warehouse: the RWARE tiny one-agent environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
``cap.world.*`` contract from the environment's spaces.  The registered ``rware-tiny-1ag-v2`` has a Tuple of one
``Discrete(5)`` action space per agent and a Tuple of one flattened ``Box`` observation per agent, so
``cap.world.step.v1`` takes ``{ticks, action: {items: [index]}}``, ``cap.world.reset.v1`` takes ``{seed, options}``
and ``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware backend and no
operator-required limit.

The gate does not install or import ``rware`` (it needs gymnasium, numpy, networkx and pyglet), so the ``fake``
backend is this package's pure Python ``FakeWarehouse`` (fake.py).  A backend name that ``backends`` does not list
(``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path needs the upstream package
and was not run here.  The upstream ``Warehouse.step`` returns one reward per agent (a list) while the Gymnasium
bridge carries one scalar reward; the registered layout has one agent, and the fake returns that single value.  The
``fidelity`` contract is F0: a discrete grid-world with no continuous dynamics, no physical timestep and no wall-clock
pacing.  Every constant and rule cites a line of the clone at the pinned commit
96fbc64e3eae5fee915e0d390f864fa06ddccd47.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

WAREHOUSE = "rware/warehouse.py"
REGISTRATION = "rware/__init__.py"


class RwareTiny(GymnasiumDriver):
    device_id = "rware-tiny-1ag"
    env_id = "rware-tiny-1ag-v2"
    native = "rware.warehouse:Warehouse"
    backends = {"fake": ".fake:FakeWarehouse"}
    display_name = "RWARE tiny warehouse with one agent"
    vendor, model = "Semitable", "rware-tiny-1ag-v2"
    tags = ["rware", "warehouse", "multi-robot", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The normal registration loop registers rware-{size}-{agents}ag{diff}-v2 with entry_point "
             "rware.warehouse:Warehouse for the tiny, small, medium and large layouts, the default, easy and hard "
             "difficulties and 1 to 19 agents; for tiny, 1 agent and the default difficulty the id is "
             "rware-tiny-1ag-v2", source="upstream_code", ref=f"{REGISTRATION}:7-39"),
        Fact("The registered tiny layout uses column_height 8, shelf_rows 1, shelf_columns 3, n_agents 1, "
             "msg_bits 0, sensor_range 1, request_queue_size 1, max_inactivity_steps None, max_steps 500 and "
             "individual rewards", source="upstream_code", ref=f"{REGISTRATION}:27-38"),
        Fact("The Action enum has five actions: NOOP=0, FORWARD=1, LEFT=2, RIGHT=3 and TOGGLE_LOAD=4",
             source="upstream_code", ref=f"{WAREHOUSE}:31-36"),
        Fact("The action space is a Tuple with one Discrete(len(Action)) per agent, which is a Tuple of one "
             "Discrete(5) for the registered one-agent layout", source="upstream_code", ref=f"{WAREHOUSE}:255-260"),
        Fact("The Direction enum has four values: UP=0, DOWN=1, LEFT=2 and RIGHT=3", source="upstream_code",
             ref=f"{WAREHOUSE}:39-44"),
        Fact("The default observation space is built by _use_fast_obs: it flattens each per-agent sub-space of the "
             "slow observation space into a Box and returns a Tuple with one Box per agent", source="upstream_code",
             ref=f"{WAREHOUSE}:505-522"),
        Fact("The sensor window of an agent has (1 + 2 * sensor_range) ** 2 cells, which is a 3x3 window at the "
             "registered sensor_range 1", source="upstream_code", ref=f"{WAREHOUSE}:432-437"),
        Fact("The grid height is (column_height + 1) * shelf_rows + 2 and its width is (2 + 1) * shelf_columns + 1; "
             "the goals are the two cells in the middle of the last row", source="upstream_code",
             ref=f"{WAREHOUSE}:294-306"),
        Fact("A reset recreates the shelves, spawns the agents at random grid locations with random directions and "
             "samples the request queue from the shelves using np_random", source="upstream_code",
             ref=f"{WAREHOUSE}:757-799"),
        Fact("step maps each tuple element to an Action and a forward move of an agent carrying a shelf into a "
             "standing shelf is cancelled to NOOP", source="upstream_code", ref=f"{WAREHOUSE}:804-844"),
        Fact("A requested shelf delivered to a goal is replaced in the request queue by a uniformly sampled shelf "
             "that is not currently requested", source="upstream_code", ref=f"{WAREHOUSE}:905-918"),
        Fact("With RewardType.INDIVIDUAL the agent that delivers a requested shelf to a goal receives +1",
             source="upstream_code", ref=f"{WAREHOUSE}:919-924"),
        Fact("The episode reports done when max_inactivity_steps or max_steps is reached; truncated is always False",
             source="upstream_code", ref=f"{WAREHOUSE}:936-942"),
        Fact("The environment metadata declares the render modes human and rgb_array at 10 frames per second",
             source="upstream_code", ref=f"{WAREHOUSE}:141-143"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2): a discrete grid world, not a
    #: continuous physics model.  The bridge derives the engine, the seeded determinism and the lockstep clock;
    #: they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:rware-tiny-1ag-v2",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the agent positions, directions and request queue, and "
                     "the transitions are deterministic; this package's fake draws from Python's random.Random "
                     "while upstream draws from numpy's np_random, so one seed does not give the same trajectory "
                     "on the two implementations",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the environment is a discrete grid-world kinematic model: positions, headings, shelf pick-up and "
            "delivery and episode counters are modelled directly; there are no continuous dynamics, forces, "
            "contacts, actuators or sensors",
            "no wall-clock pacing: realtime_factor 0 and the environment has no physical timestep, so timestep_ms "
            "is 0 and one tick advances one discrete transition (warehouse.py:933-946); a receipt reports tick, "
            "not simulated milliseconds",
            "the Gymnasium bridge carries one scalar reward while upstream Warehouse.step returns one reward per "
            "agent (warehouse.py:946); the registered layout has one agent, so the fake returns that single "
            "reward as a float",
            "the fake backend re-implements the one-agent tiny layout in pure Python and was not compared with a "
            "run of the upstream environment; it seeds Python's random.Random instead of numpy's np_random and "
            "has no multi-agent collision graph, rendering or gymnasium wrapper chain",
            "snapshot and restore are not offered: Warehouse exposes no get_state or set_state",
        ],
    }
