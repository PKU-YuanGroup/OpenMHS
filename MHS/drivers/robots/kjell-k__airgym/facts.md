# Facts and tags for gh.kjell-k/airgym

Every fact cites its source at commit `818749ab1e93f41e1f1cf62a98f15ee9e4461568`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| AirSimEnv is the Gym environment class a user instantiates; it derives from gym.Env and uses gym spaces | upstream_code | gym_airsim/envs/AirGym.py:18-27 |
| The observation space is a Box with low 0, high 255 and shape (30, 100); the state starts as uint8 zeros of the same shape | upstream_code | gym_airsim/envs/AirGym.py:24-25 |
| The action space is Discrete(3) | upstream_code | gym_airsim/envs/AirGym.py:27 |
| The flight goal is global xy (221.0, -9.0) | upstream_code | gym_airsim/envs/AirGym.py:29 |
| The distance log starts at 221 and the track log at -2 for every episode | upstream_code | gym_airsim/envs/AirGym.py:35-38 |
| The environment uses the legacy Gym methods _step and _reset, not the current Gymnasium reset/step API | upstream_code | gym_airsim/envs/AirGym.py:75-127 |
| A step asserts the action is in the action space, forwards it to airgym.take_action, then reads getPosition and goal_direction | upstream_code | gym_airsim/envs/AirGym.py:75-85 |
| The distance reward is -1 plus the distance closed since the previous step (distance_before - distance_now) | upstream_code | gym_airsim/envs/AirGym.py:60-70 |
| A collision ends the episode with reward -100; the code also ends it with reward 0 when take_action returns 99 | upstream_code | gym_airsim/envs/AirGym.py:87-94 |
| Reaching within 3 of the goal ends the episode with reward 100 | upstream_code | gym_airsim/envs/AirGym.py:99-102 |
| A cumulative reward below -100 ends the episode | upstream_code | gym_airsim/envs/AirGym.py:109-112 |
| A step returns the depth observation, reward, done and an info object with x_pos and y_pos | upstream_code | gym_airsim/envs/AirGym.py:117-120 |
| A reset calls AirSim_reset, clears the logs and returns the depth observation | upstream_code | gym_airsim/envs/AirGym.py:134-150 |
| The depth observation is 10 goal-direction rows on top of 20 depth rows, 100 columns wide, and the goal line is mapped from track over -180..180 onto 0..100 | upstream_code | gym_airsim/envs/myAirSimClient.py:137-153 |
| The depth image comes from AirSim's DepthPerspective camera, inverted and gamma-corrected with factor 10 before resizing | upstream_code | gym_airsim/envs/myAirSimClient.py:121-139 |
| Action 0 flies straight for 1 s at 4 m/s, action 1 yaws right for 0.8 s, action 2 yaws left for 1 s | upstream_code | gym_airsim/envs/myAirSimClient.py:70-102 |
| straight moves along the current heading at the requested speed with moveByVelocityZ at z=-6 | upstream_code | gym_airsim/envs/myAirSimClient.py:31-39 |
| yaw_right commands 30 deg/s and yaw_left commands -30 deg/s | upstream_code | gym_airsim/envs/myAirSimClient.py:41-49 |
| The README documents the three actions as straight 4 m/s for 1 s, right yaw 26 deg/s for 1 s and left yaw 30 deg/s for 1 s | vendor_doc | README.md:34-38 |
| MultirotorClient defaults the AirSim address to 127.0.0.1 and passes port 41451 to AirSimClientBase | upstream_code | AirSimClient.py:426-430 |
| AirSimClientBase opens a msgpackrpc Client to that address and port | upstream_code | AirSimClient.py:148-150 |
| The README says the repository is not maintained anymore and new AirSim versions are very likely incompatible | vendor_doc | README.md:1 |
| The Gym registration of AirSimEnv-v42 is commented out; the module only imports register | upstream_code | gym_airsim/__init__.py:1-7 |

Limits: the driver declares none of its own. The only action bound is the environment's action space
(`Discrete(3)`, so `action.index` is 0 to 2), which the Gymnasium bridge derives from the fake, with the source
`upstream_code` and the ref `gym_airsim/envs/AirGym.py:27`; `ticks` is bounded 1 to `max_ticks` (10000 by default) by
the bridge. The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `airsim-gym:AirSimEnv`, level F0 (kinematic/analytic, no
dynamics), determinism `seeded` with `seed_control` `parameter`, timestep 1000 ms (one action interval; README.md:35-38
documents the actions as lasting 1 s), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore.
The gaps say what is not modelled: AirSim physics, collision, the DepthPerspective camera, wall-clock waits and the
comparison with the upstream environment, which was never run. They also say that the synthetic depth rows are a
fixed per-episode texture and that the bridge's reset `options` object is ignored (`AirSimEnv._reset` takes no
arguments, gym_airsim/envs/AirGym.py:127).

The fake's numbers are test data: the starting pose `(0, 0)` facing the goal, the default reset seed 0, the
`# placeholder` depth texture and the two image fill values. No such value is used as a fact, a limit or a reference.
The constants copied from the clone cite their line in fake.py.

Safety: a simulated R0 device. There is no hardware backend and no native stop; an e-stop is the runtime's software
latch. After it, every step and reset is refused until `mhs.safety.reset` clears the latch, and the last observation
stays readable.

Tags: airsim, quadrotor, depth-camera, reinforcement-learning, simulation, gymnasium
