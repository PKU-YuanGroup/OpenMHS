# Facts and tags for gh.angel-ayala/gym-webots-drone

Every fact cites its source at commit `24eb199041403d108bc94fac0f522cb33a544c9c`: `upstream_code` (a Python source
line of the clone) or `vendor_doc` (README.md). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| webots_drone registers webots_drone/DroneEnvContinuous-v0 with entry point webots_drone.envs:DroneEnvContinuous | upstream_code | webots_drone/__init__.py:23-26 |
| DroneEnvContinuous is a gym.Env whose action space is a Box built from the simulation's control ranges | upstream_code | webots_drone/envs/drone_continuous.py:56-59 |
| The Mavic control ranges are pi/12 rad for roll, pi/12 rad for pitch, pi rad for yaw and 5 for altitude, returned as symmetric low and high limits | upstream_code | webots_drone/webots_simulation.py:78-87 |
| The 22-element vector observation is orientation and angular velocity, position and speed, north_rad and nine distance sensors | upstream_code | webots_drone/envs/preprocessor.py:26-88 |
| With is_pixels=False the observation space is a 22-element float32 Box with infinite bounds | upstream_code | webots_drone/envs/drone_continuous.py:70-76 |
| The default observation configuration is a 3x84x84 uint8 camera image | upstream_code | webots_drone/envs/drone_continuous.py:61-69 |
| The forest_fire world's basic time step is 8 ms | upstream_code | worlds/forest_fire.wbt:14 |
| The forest_fire world's FlightArea is 100 by 100 | upstream_code | worlds/forest_fire.wbt:33-37 |
| The constructor defaults are time_limit_seconds=60, max_no_action_seconds=5, frame_skip=125 (commented 1 s), goal_threshold=5, init_altitude=25, altitude_limits=[11,75], target_pos=2, target_dim=[7,3.5] and is_pixels=True | upstream_code | webots_drone/envs/drone_continuous.py:43-52 |
| set_reaction_intervals sets the frame interval to frame_skip - 5 to frame_skip + 5 | upstream_code | webots_drone/envs/drone_continuous.py:119-120 |
| step draws the number of Webots steps from the frame interval with the environment's numpy generator | upstream_code | webots_drone/envs/drone_continuous.py:461-463 |
| The time limit and no-action limit are converted to Webots steps from the simulation's basic time step | upstream_code | webots_drone/envs/drone_continuous.py:79-82 |
| get_flight_area halves the world's FlightArea size and appends the altitude limits | upstream_code | webots_drone/webots_simulation.py:89-95 |
| reset calls seed, sim.reset, play_fast, sync, set_target and lift_uav, then returns the state and info | upstream_code | webots_drone/envs/drone_continuous.py:442-454 |
| step returns observation, reward, terminated, truncated and info | upstream_code | webots_drone/envs/drone_continuous.py:498 |
| The reward combines orientation, distance, velocity and elevation terms | upstream_code | webots_drone/reward.py:62-66 |
| A goal adds 10 to the reward and truncates the episode, and a terminal state subtracts 2 | upstream_code | webots_drone/envs/drone_continuous.py:482-491 |
| The final states are no action, flipped, max distance, inside risk zone and out of flight area | upstream_code | webots_drone/envs/drone_continuous.py:264-289 |
| The seed method seeds the environment generator, the simulation and the virtual target | upstream_code | webots_drone/envs/drone_continuous.py:151-161 |
| The environment is an interface for Webots R2023b and needs WEBOTS_HOME and LD_LIBRARY_PATH set | vendor_doc | README.md:220-224 |
| The dependencies are gym==0.26.0, simple_pid==2.0.0 and opencv-python==4.8.1.* | upstream_code | setup.py:25-27 |

Limits: the driver declares none of its own. The step action space is the bound, and the Gymnasium bridge derives it
from the environment object the driver serves (`FakeDroneEnv` on the fake backend): `action.values[0]` roll and
`action.values[1]` pitch are `+-pi/12`, `action.values[2]` yaw is `+-pi` and `action.values[3]` altitude is `+-5`
(`webots_simulation.py:81-86` via `drone_continuous.py:56-59` and `:128-130`); `ticks` is the bridge's 1 to 10000.
The device is simulated (R0), so no limit is `operator_required`; nothing in the clone states a different bound for
the configured vector-observation environment.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `webots`, level F0 (kinematic stand-in, no dynamics claim),
determinism `seeded` with `seed_control` `parameter`, nominal timestep 1000 ms (one `env.step` is a random 120-130
Webots base steps of 8 ms, so 960-1040 ms), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The gaps say what is not modelled, that the default 3x84x84 camera observation is **NOT COVERED** and that
the sim backend (`gym.make`) was not run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

The fake backend is model data, not a fact source: `ATTITUDE_TO_SPEED`, `START_POSITION`, `START_ORIENTATION`,
`DIST_SENSORS` and `TARGET_POSITION` are marked `# placeholder` in `fake.py` and are never cited here or in
`driver.py`.

Tags: webots, drone, uav, reinforcement-learning, simulation, gym
