# Facts and tags for gh.tobirohrer/building-energy-storage-simulation

Every fact cites its source at commit `05b9197c8d6f600bed2a5b092db6de6f07bf3c65`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or
`upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The action space is Box(low=-1, high=1, shape=(1,)): one float per step, the fraction of the battery's maximum charge per time step | upstream_code | building_energy_storage_simulation/environment.py:45 |
| A step multiplies the action by max_battery_charge_per_timestep and passes the result to the battery | upstream_code | building_energy_storage_simulation/building_simulation.py:90 |
| The battery trims the charge or discharge amount to +-max_battery_charge_per_timestep and clamps the state of charge to 0..capacity | upstream_code | building_energy_storage_simulation/battery.py:34-52 |
| Electricity consumption is the battery energy plus the load minus the solar generation, and a negative value is trimmed to 0 so surplus solar energy is not fed into the grid | upstream_code | building_energy_storage_simulation/building_simulation.py:91-95 |
| The reward is -1 * electricity_consumption * electricity_price | upstream_code | building_energy_storage_simulation/environment.py:147-148 |
| The observation concatenates the battery state of charge with the load, solar and price forecasts, 3*n+1 numbers in that order | upstream_code | building_energy_storage_simulation/environment.py:129-133 |
| The observation space is Box(-inf, inf, shape=(num_forecasting_steps*3+1,)) | upstream_code | building_energy_storage_simulation/environment.py:49-52 |
| step returns terminated when step_count reaches max_timesteps and truncated is always False | upstream_code | building_energy_storage_simulation/environment.py:109-115 |
| Environment.reset() calls BuildingSimulation.reset() | upstream_code | building_energy_storage_simulation/environment.py:73 |
| BuildingSimulation.reset() resets the battery state of charge and sets step_count to 0 | upstream_code | building_energy_storage_simulation/building_simulation.py:51-61 |
| With randomize_start_time_step the reset draws start_index from numpy's global uniform generator; the seed argument of reset is not used | upstream_code | building_energy_storage_simulation/environment.py:61-77 |
| The Environment constructor defaults max_timesteps to 2000 and num_forecasting_steps to 4 | upstream_code | building_energy_storage_simulation/environment.py:29-30 |
| The constructor asserts that max_timesteps plus num_forecasting_steps is not greater than the profile length | upstream_code | building_energy_storage_simulation/environment.py:42-43 |
| The default profiles are loaded from the package's data/preprocessed CSVs: electricity_load_profile.csv, solar_generation_profile.csv and electricity_price_profile.csv | upstream_code | building_energy_storage_simulation/building_simulation.py:27-30 |
| BuildingSimulation converts a scalar electricity_price into a constant profile of the same length as the solar generation profile | upstream_code | building_energy_storage_simulation/building_simulation.py:38-41 |
| Environment.step takes the first element of an iterable action and passes it to the simulation without checking it against the action space; the OpenMHS runtime enforces the Box bound instead | upstream_code | building_energy_storage_simulation/environment.py:104-106 |
| The documented usage constructs Environment(building_simulation=simulation) and then calls env.reset() and env.step(1) | vendor_doc | README.md:29-37 |
| The README documents the action interval [-1;1]: 1 is maximum charging defined by max_battery_charge_per_timestep, -1 maximum discharging and 0 neither | vendor_doc | README.md:66-74 |
| The README documents the observation table: the state of charge in kWh, then n load, n solar and n price forecasts | vendor_doc | README.md:78-83 |
| The README states that the episode ends when max_timesteps is reached | vendor_doc | README.md:94-96 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the
environment (`Box(-1, 1, (1,))`: `action.values` from -1 to 1 per element, source `upstream_code`, ref
`building_energy_storage_simulation/environment.py:45`, the line where the clone states the bound), and `ticks` (1 to
`max_ticks`, 10000 by default). The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:building-energy-storage-simulation`, level F0
(analytic energy accounting: one profile row per step, an ideal battery with a state of charge, no dynamics), determinism
`seeded` with `seed_control` `parameter`, `timestep_ms` 0 (the Environment class declares no duration for one step),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled and that
this package's fake was never compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: building-energy, battery, solar, energy-management, reinforcement-learning, simulation, gymnasium
