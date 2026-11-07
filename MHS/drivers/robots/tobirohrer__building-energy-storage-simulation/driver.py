"""OpenMHS driver for gh.tobirohrer/building-energy-storage-simulation: a Gymnasium building-battery world.

A GymnasiumDriver is configuration only: the bridge derives the contract from the environment's spaces.  Upstream
the environment is not registered with ``gymnasium.make``: it is constructed with a ``BuildingSimulation``
(README.md:29-37), so ``env_id`` is left unset and the ``fake`` backend is the package's own pure Python
re-implementation (fake.py).  A backend name that ``backends`` does not list is not served.

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{values}`` bounded by the environment's
``Box(-1, 1, (1,))`` (environment.py:45); ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` takes ``{seed}``.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every fact and rule cites a line of the clone at the pinned commit (05b9197c8d6f600bed2a5b092db6de6f07bf3c65).
This package is model-authored and unreviewed: it is checked on the fake backend only, and the fake was never
compared with the upstream environment.
"""

from mhs.driver import Fact, GymnasiumDriver

ENVIRONMENT = "building_energy_storage_simulation/environment.py"
SIMULATION = "building_energy_storage_simulation/building_simulation.py"
BATTERY = "building_energy_storage_simulation/battery.py"


class BuildingEnergyStorageSimulation(GymnasiumDriver):
    device_id = "building-energy-storage-simulation"
    native = "building_energy_storage_simulation.environment:Environment"
    backends = {"fake": ".fake:FakeEnvironment"}
    action_space_ref = f"{ENVIRONMENT}:45"
    display_name = "Building Energy Storage Simulation (battery, solar and price-varying grid)"
    vendor, model = "Tobias Rohrer", "building-energy-storage-simulation"
    tags = ["building-energy", "battery", "solar", "energy-management", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("The action space is Box(low=-1, high=1, shape=(1,)): one float per step, the fraction of the battery's "
             "maximum charge per time step", source="upstream_code", ref=f"{ENVIRONMENT}:45"),
        Fact("A step multiplies the action by max_battery_charge_per_timestep and passes the result to the battery",
             source="upstream_code", ref=f"{SIMULATION}:90"),
        Fact("The battery trims the charge or discharge amount to +-max_battery_charge_per_timestep and clamps the "
             "state of charge to 0..capacity", source="upstream_code", ref=f"{BATTERY}:34-52"),
        Fact("Electricity consumption is the battery energy plus the load minus the solar generation, and a negative "
             "value is trimmed to 0 so surplus solar energy is not fed into the grid", source="upstream_code",
             ref=f"{SIMULATION}:91-95"),
        Fact("The reward is -1 * electricity_consumption * electricity_price", source="upstream_code",
             ref=f"{ENVIRONMENT}:147-148"),
        Fact("The observation concatenates the battery state of charge with the load, solar and price forecasts, "
             "3*n+1 numbers in that order", source="upstream_code", ref=f"{ENVIRONMENT}:129-133"),
        Fact("The observation space is Box(-inf, inf, shape=(num_forecasting_steps*3+1,))", source="upstream_code",
             ref=f"{ENVIRONMENT}:49-52"),
        Fact("step returns terminated when step_count reaches max_timesteps and truncated is always False",
             source="upstream_code", ref=f"{ENVIRONMENT}:109-115"),
        Fact("Environment.reset() calls BuildingSimulation.reset()", source="upstream_code",
             ref=f"{ENVIRONMENT}:73"),
        Fact("BuildingSimulation.reset() resets the battery state of charge and sets step_count to 0",
             source="upstream_code", ref=f"{SIMULATION}:51-61"),
        Fact("With randomize_start_time_step the reset draws start_index from numpy's global uniform generator; the "
             "seed argument of reset is not used", source="upstream_code", ref=f"{ENVIRONMENT}:61-77"),
        Fact("The Environment constructor defaults max_timesteps to 2000 and num_forecasting_steps to 4",
             source="upstream_code", ref=f"{ENVIRONMENT}:29-30"),
        Fact("The constructor asserts that max_timesteps plus num_forecasting_steps is not greater than the profile "
             "length", source="upstream_code", ref=f"{ENVIRONMENT}:42-43"),
        Fact("The default profiles are loaded from the package's data/preprocessed CSVs: electricity_load_profile.csv, "
             "solar_generation_profile.csv and electricity_price_profile.csv", source="upstream_code",
             ref=f"{SIMULATION}:27-30"),
        Fact("BuildingSimulation converts a scalar electricity_price into a constant profile of the same length as the "
             "solar generation profile", source="upstream_code", ref=f"{SIMULATION}:38-41"),
        Fact("Environment.step takes the first element of an iterable action and passes it to the simulation without "
             "checking it against the action space; the OpenMHS runtime enforces the Box bound instead",
             source="upstream_code", ref=f"{ENVIRONMENT}:104-106"),
        Fact("The documented usage constructs Environment(building_simulation=simulation) and then calls env.reset() "
             "and env.step(1)", source="vendor_doc", ref="README.md:29-37"),
        Fact("The README documents the action interval [-1;1]: 1 is maximum charging defined by "
             "max_battery_charge_per_timestep, -1 maximum discharging and 0 neither", source="vendor_doc",
             ref="README.md:66-74"),
        Fact("The README documents the observation table: the state of charge in kWh, then n load, n solar and n "
             "price forecasts", source="vendor_doc", ref="README.md:78-83"),
        Fact("The README states that the episode ends when max_timesteps is reached", source="vendor_doc",
             ref="README.md:94-96"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    fidelity_level = "F0"
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "analytic:building-energy-storage-simulation",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the dynamics are deterministic; upstream reset(seed) ignores the seed and, with "
                     "randomize_start_time_step, draws the start index from numpy's global generator, while this "
                     "package's fake seeds a private random.Random when a seed is supplied, so a seed does not give "
                     "the same trajectory on the two; no snapshot or restore exists, so repeatability is claimed "
                     "only for a fresh world",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "analytic energy accounting, not a physical model: one row of the supplied profiles per step, an ideal "
            "battery with only a state of charge, and no electrical, thermal, aging, efficiency, inverter or "
            "control dynamics, no forces or contacts and no actuator, sensor or noise model",
            "timestep_ms is 0 because the Environment class declares no duration for one time step; a step consumes "
            "one row of the load, solar and price profiles, and ticks advance that row index (fidelity F0 is not a "
            "claim about elapsed time)",
            "no wall-clock pacing: realtime_factor 0 and only commands advance the world",
            "the fake backend synthesizes placeholder profile rows and re-implements Environment, BuildingSimulation "
            "and Battery in pure Python; it was not compared with the upstream environment (gymnasium is not "
            "importable where the gate runs), so observations, rewards and prices are not the bundled CSV data and "
            "the fake returns Python float lists where upstream returns a numpy array",
            "the fake's optional forecast randomisation changes only the returned copy, while upstream adds the noise "
            "in place to a numpy slice of the stored profile",
            "no rendering (upstream render is a no-op), no snapshot or restore (the environment has no "
            "get_state/set_state pair), and reset options are accepted and ignored as the upstream reset ignores them",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
