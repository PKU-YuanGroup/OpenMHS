# Facts and tags for gh.axelbr/racecar_gym

Every fact cites its source at commit `70496767d80397010ac9b5ba722647ca67e3f85c`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or `upstream_code`
(`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| SingleAgentRaceEnv is the single-agent Gymnasium environment of the gym API | upstream_code | racecar_gym/envs/gym_api/single_agent_race.py:9 |
| A scenario that lists no actuators gets the VehicleSpec default ['steering', 'motor'] | upstream_code | racecar_gym/core/specs.py:23 |
| The vehicle action space is a Dict keyed by actuator name | upstream_code | racecar_gym/core/vehicles.py:40-41 |
| The motor actuator's action space is Box(low=-1.0, high=1.0, shape=(1,)) | upstream_code | racecar_gym/bullet/actuators.py:62 |
| The steering actuator's action space is Box(low=-1.0, high=1.0, shape=(1,)) | upstream_code | racecar_gym/bullet/actuators.py:117 |
| The car's action space is normalized between -1 and 1 | vendor_doc | README.md:90 |
| The vehicle observation space is a Dict keyed by sensor name | upstream_code | racecar_gym/core/vehicles.py:44-46 |
| The single-agent observation space adds a 'time' Box with declared bounds 0 to 1 to the agent's sensor Dict | upstream_code | racecar_gym/envs/gym_api/single_agent_race.py:24-27 |
| The step writes the growing simulation time into observation['time'] without clipping it to the declared Box bound | upstream_code | racecar_gym/envs/gym_api/single_agent_race.py:38 |
| The shipped austria scenario requests the lidar, pose, velocity and acceleration sensors | upstream_code | scenarios/austria.yml:7 |
| The racecar lidar is configured with 1080 rays, range 15.0 and min_range 0.25 | upstream_code | models/vehicles/racecar/racecar.yml:55-57 |
| The lidar space is a Box of one value per ray bounded by min_range and min_range+range | upstream_code | racecar_gym/bullet/sensors.py:109-112 |
| A world update advances pybullet by one simulation step and adds the configured time step to the state time | upstream_code | racecar_gym/bullet/world.py:120-122 |
| The SimulationSpec time step defaults to 0.01 s | upstream_code | racecar_gym/core/specs.py:8 |
| The fixed-timestep sensor scheduler is constructed with a 0.01 s time step | upstream_code | racecar_gym/bullet/providers.py:67 |
| The single-agent reset passes the seed to gymnasium.Env.reset | upstream_code | racecar_gym/envs/gym_api/single_agent_race.py:44 |
| Sensor noise is drawn from numpy's global generator (np.random.normal), so the seed passed to gymnasium.Env.reset does not control it | upstream_code | racecar_gym/bullet/sensors.py:255 |
| The reset option 'mode' selects the starting-position mode and defaults to 'grid' | upstream_code | racecar_gym/envs/gym_api/single_agent_race.py:50-53 |
| The maximize_progress task's default progress_reward is 100.0 | upstream_code | racecar_gym/tasks/progress_based.py:8 |
| The maximize_progress reward is the change in lap+progress times progress_reward | upstream_code | racecar_gym/tasks/progress_based.py:20-33 |
| The maximize_progress task ends when lap > laps or time > time_limit | upstream_code | racecar_gym/tasks/progress_based.py:35-39 |
| The single-agent registration passes the scenario path as the scenario kwarg | upstream_code | racecar_gym/envs/gym_api/__init__.py:23-29 |
| The gym_api module registers one SingleAgent<Track>-v0 environment per scenario file | upstream_code | racecar_gym/envs/gym_api/__init__.py:43-47 |
| SingleAgentAustria-v0 is documented as a predefined environment id | vendor_doc | README.md:132 |

Limits: the driver declares none. The only input bounds are the action space, which the bridge derives from the fake
environment (`action.motor` and `action.steering`, each from -1.0 to 1.0 with no source and ref
`action_space of the fake backend .fake:FakeSingleAgentRaceEnv`), and `ticks` (1 to 10000, the bridge's
`max_ticks`). The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `pybullet`, level F2 (rigid-body dynamics with contacts,
actuator control and noisy sensors), determinism `statistical` (the reset seed does not control the global numpy
sensor noise), timestep 10 ms (the in-clone `SimulationSpec` default and the fixed sensor scheduler; the downloaded
scene supplies the world's actual `time_step`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The gaps say what the fake does not model and that the real scene files are not in the clone.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: racecar, racing, reinforcement-learning, pybullet, simulation, gymnasium
