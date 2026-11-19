# Facts and tags for gh.hoangtranngoc/airsim-rl

Every fact cites its source at commit `b4700049d8c2c519476d4ee15f2504795f80df9d`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| README describes experiments with deep reinforcement learning on a car and a UAV in AirSim, an external simulator | vendor_doc | README.md:2 |
| The setup instructions say to build AirSim and Unreal Engine 4 (UE4) on Windows | vendor_doc | README.md:17 |
| The setup instructions name gym 0.17.2 as the Gym version used by the experiments | vendor_doc | README.md:19 |
| AirSimCarEnv subclasses gym.Env | upstream_code | gym_airsim/airsim_car_env.py:12 |
| The environment reads config.ini from the repository root | upstream_code | gym_airsim/airsim_car_env.py:21-22 |
| The action space is Discrete(int(config['car_agent']['actions'])) | upstream_code | gym_airsim/airsim_car_env.py:26 |
| The shipped config.ini sets actions = 7 | upstream_code | config.ini:24 |
| The shipped config.ini sets image_height 144, image_width 256 and image_channels 3 | upstream_code | config.ini:3-5 |
| The observation space is a Box of low 0, high 255 and shape (image_height, image_width, image_channels) with dtype uint8 | upstream_code | gym_airsim/airsim_car_env.py:28-36 |
| The shipped config.ini sets track_width = 12 | upstream_code | config.ini:7 |
| step moves the car with the action, reads the car state and the car controls, computes the reward and the done flag, gets the camera observation and returns the legacy four-tuple (observation, reward, done, info) | upstream_code | gym_airsim/airsim_car_env.py:40-59 |
| reset restarts the car agent, gets a camera observation and returns the observation only | upstream_code | gym_airsim/airsim_car_env.py:61-65 |
| close calls the car agent's AirSim reset | upstream_code | gym_airsim/airsim_car_env.py:70-72 |
| The reward is computed from the perpendicular distance between the car and the line through the two closest waypoints, using the configured track width | upstream_code | gym_airsim/airsim_car_env.py:74-85 |
| The episode is done when the reward is negative, or when the car is less than 5 m from the last waypoint | upstream_code | gym_airsim/airsim_car_env.py:87-98 |
| The reward markers are 0.1, 0.25 and 0.5 times the track width and the rewards are 1, 0.5, 0.1 and -1 outside the third marker | upstream_code | utils.py:14-27 |
| CarAgent subclasses the AirSim CarClient | upstream_code | gym_airsim/car_agent.py:7 |
| The car agent constructor connects to the AirSim simulator, confirms the connection and enables API control | upstream_code | gym_airsim/car_agent.py:8-12 |
| The discrete steering values are built from steering_max and steering_granularity and the maximum steering value is appended | upstream_code | gym_airsim/car_agent.py:26-28 |
| restart calls the AirSim reset and then enables API control again | upstream_code | gym_airsim/car_agent.py:34-36 |
| observe requests the front camera scene image and reshapes the returned bytes to the configured image shape | upstream_code | gym_airsim/car_agent.py:38-48 |
| move interprets the action and sends the resulting controls with setCarControls | upstream_code | gym_airsim/car_agent.py:50-52 |
| In action mode 0 the throttle is the fixed configured value and the steering is steering_values[action]; action modes 1 and 2 return NotImplemented | upstream_code | gym_airsim/car_agent.py:54-66 |
| The car agent fetches waypoints whose names match the configured regular expression, sorts them and reads each object's pose | upstream_code | gym_airsim/car_agent.py:68-79 |
| The two closest waypoints are the endpoints of the segment with the smallest summed distance from the car | upstream_code | gym_airsim/car_agent.py:84-97 |
| train.py constructs the environment as AirSimCarEnv(), the user-facing training interface | upstream_code | train.py:50 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the fake's
`Discrete(7)`: `action.index` from 0 to 6, with no source and a ref identifying the fake backend. The fake copies
the shipped count in `config.ini:24`, but `gym_airsim/airsim_car_env.py:26` reads that separate configuration file
and does not itself state the resulting numeric index range, so no `action_space_ref` is assigned. `ticks` is bounded by the bridge (1 to `max_ticks`, 10000 by default).
The device is simulated (R0), so no limit is `operator_required` and no `site-limits.example.json` is shipped.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine is an analytic legacy-Gym AirSim car-track stand-in, level
F0 (no AirSim, Unreal Engine, physics or camera), determinism `exact` with `seed_control` `none`, timestep 0 ms
(one synthetic transition per step; AirSim advances continuously), `realtime_factor` 0, clock `lockstep`, reset
`full`, no snapshot and restore. The gaps say what is not modelled, that the fake is not a recording, that the real
camera frame is 144 x 256 x 3 and is NOT COVERED, and that no live AirSim run exists.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step,
reset or seed is accepted until `mhs.safety.reset` clears the latch, and the state stays readable. The latch calls
nothing in AirSim, and this package offers no live backend.

Tags: airsim, unreal-engine, car, legacy-gym, reinforcement-learning, simulation, camera

Native construction caveats (unserved): `CarAgent.observe` retries until the image byte count matches with no
retry bound (`gym_airsim/car_agent.py:39-48`); the constructor prints waypoint names to stdout (`:68-77`).
A live adapter would need bounded image acquisition and separation from an MHS stdio server. Only the fake stops
when MHS latches; the package sends no AirSim stop and provides no seeded live-trajectory evidence.
