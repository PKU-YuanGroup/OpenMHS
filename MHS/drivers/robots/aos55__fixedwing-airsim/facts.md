# Facts and tags for gh.aos55/fixedwing-airsim

The package serves `envs.single_observation:SingleObservation` at commit
`c5054486fb05dc67668b123c7789e399c8d4ce02`.  Every fact below is also declared in `driver.py`; the generated
`reference.json`/`REFERENCE.md` are built from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| `SingleObservation` is the OpenAI Gym environment class of the package (a `gym.Env` subclass) | upstream_code | `src/envs/single_observation.py:13` |
| The action space is `Box(2)`: heading from -45 to +45 degrees and pitch from -30 to 0 degrees | upstream_code | `src/envs/single_observation.py:62-68` |
| The action space is built as `spaces.Box(min_angle, max_angle, dtype=np.float32)` from the four angle attributes | upstream_code | `src/envs/single_observation.py:66-68` |
| The observation space is `spaces.Box(low=0, high=255)` with the shape and dtype of the first AirSim Scene image | upstream_code | `src/envs/single_observation.py:69-71` |
| An AirSim Scene image is reshaped to `(3, image_response.height, image_response.width)`; the resolution comes from the AirSim response at runtime | upstream_code | `src/image_processing.py:41-50` |
| The step reads the Scene image before the physics update and reports `done=True` when AirSim reports `collision_info.has_collided` | upstream_code | `src/envs/single_observation.py:88-100` |
| The reward is 1 when the collided `object_name` is `airport` and 0 otherwise | upstream_code | `src/envs/single_observation.py:93-100` |
| A step advances JSBSim once and returns `(observation, reward, done, info)` | upstream_code | `src/envs/single_observation.py:104-113` |
| A reset reinitialises the `Simulation` and returns a new Scene image | upstream_code | `src/envs/single_observation.py:121-130` |
| The `seed` method forwards to `gym.utils.seeding.np_random` and returns `[seed]` | upstream_code | `src/envs/single_observation.py:81-83` |
| The environment uses `airsim_frequency_hz` 48.0, `jsbsim_frequency_hz` 240.0 and `airspeed` 50.0, and constructs `Simulation` with the JSBSim frequency | upstream_code | `src/envs/single_observation.py:49-58` |
| The environment's default aircraft is the `x8` model | upstream_code | `src/envs/single_observation.py:52` |
| `Simulation` sets `sim_dt = 1.0 / sim_frequency_hz` and passes it to the FDM | upstream_code | `src/jsbsim_simulator.py:85-87` |
| The AirSim pose update runs when `relative_update = airsim_frequency_hz / jsbsim_frequency_hz` makes the integer graphics tick increase | upstream_code | `src/envs/single_observation.py:76-105` |
| The constructor computes `max_updates = max_sim_time * jsbsim_frequency_hz`, but `step` never compares `id` with `max_updates`, so the environment code has no episode time limit | upstream_code | `src/envs/single_observation.py:75-113` |
| The default initial conditions are `basic_ic.xml`; `minimal_ic.xml` is used only when `init_conditions` is not `None` | upstream_code | `src/jsbsim_simulator.py:139-148` |
| `Simulation.reinitialise` resets the FDM to its initial conditions | upstream_code | `src/jsbsim_simulator.py:165-176` |
| The JSBSim FDM root is the hardcoded Windows path `c:\Users\quessy\Dev\jsbsim` | upstream_code | `src/jsbsim_simulator.py:76` |
| `wall_clock_dt` starts as `None`, so the simulation is not wall-clock paced | upstream_code | `src/jsbsim_simulator.py:89` |
| `run()` advances the FDM once and sleeps only when `wall_clock_dt` is set | upstream_code | `src/jsbsim_simulator.py:178-187` |
| The AirSim client is a `VehicleClient` that calls `confirmConnection()` | upstream_code | `src/jsbsim_simulator.py:225-233` |
| The README lists AirSim and JSBSim as separate installs and requires moving the `x8` directory and `electric800w.xml` into the JSBSim aircraft and engine directories | vendor_doc | `README.md:6-10` |

## What is not covered

- The upstream environment cannot be opened here: it needs AirSim, JSBSim and a local JSBSim aircraft directory
  (`README.md:6-10`), and its `Simulation` root is a hardcoded Windows path (`src/jsbsim_simulator.py:76`).  The
  gate runs only the package fake (`fake.py`).
- The fake has no flight dynamics and no AirSim rendering.  Its observation is a 3 x 8 x 8 placeholder, not the real
  `(3, height, width)` Scene image, and its airport collision on step 50 is invented test data, marked
  `# placeholder` in `fake.py`.  The clone fixes no default image resolution for `SingleObservation`; 480 x 832 in
  `src/segmentation/config.py:22-23` belongs to the separate segmentation pipeline.
- The seed only seeds gym's `np_random`; `reset` reinitialises from `basic_ic.xml`, so the initial state does not
  depend on the seed.  Determinism is a claim about JSBSim arithmetic for a fixed state and command sequence, not
  about AirSim rendering or collision timing.
- `max_updates` is computed but never checked by `step`, so the code has no episode time limit.  Termination is the
  AirSim collision flag only; `truncated` is always false.

Tags: `fixed-wing`, `jsbsim`, `airsim`, `reinforcement-learning`, `simulation`, `gymnasium`.
