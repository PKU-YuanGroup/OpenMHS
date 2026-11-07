# Facts and tags for gh.skim0119/gym-softrobot

Every fact cites a text file of the clone at commit `e4a73ed86191747f4d0af56e612a6e339e952448`. The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| OctoMuscleCrawl-v0 registers the environment gym_softrobot.envs.octopus:OctoMuscleCrawlEnv | upstream_code | gym_softrobot/__init__.py:27-30 |
| The default configuration has 8 arms | upstream_code | gym_softrobot/envs/octopus/crawling_simulation/config.py:23 |
| OctopusMuscleConfig sets n_channels to 9 | upstream_code | gym_softrobot/envs/octopus/crawling_simulation/config.py:163-164 |
| The action space is a Box from -1.0 to 1.0 with shape (n_arms, n_channels) | upstream_code | gym_softrobot/envs/octopus/muscle_crawl_env.py:52-57 |
| The observation space is a Box with shape (6,) | upstream_code | gym_softrobot/envs/octopus/muscle_crawl_env.py:58-63 |
| The observation is the central body's displacement from its reset pose (3 values) followed by its translational velocity (3 values) | vendor_doc | docs/envs/octopus_muscle.md:123-130 |
| One step advances the simulation by one control interval, control_dt | upstream_code | gym_softrobot/envs/octopus/muscle_crawl_env.py:103 |
| The default control interval control_dt is 1/60 s | upstream_code | gym_softrobot/envs/octopus/crawling_simulation/config.py:95 |
| The default horizon is the number of control intervals in episode_duration_s | upstream_code | gym_softrobot/envs/octopus/muscle_crawl_env.py:47-49 |
| The default episode duration is five cycles of T_L = 2.4 s, 12 s | upstream_code | gym_softrobot/envs/octopus/crawling_simulation/config.py:93-101 |
| The default episode is 720 steps at 60 Hz | vendor_doc | docs/envs/octopus_muscle.md:151-153 |
| The per-step reward is forward progress along -z divided by base_length minus lateral_penalty times the absolute lateral deviation divided by base_length | upstream_code | gym_softrobot/envs/octopus/muscle_crawl_env.py:107-110 |
| base_length is 0.45 m | upstream_code | gym_softrobot/envs/octopus/crawling_simulation/config.py:29 |
| lateral_penalty is 0.5 | upstream_code | gym_softrobot/envs/octopus/crawling_simulation/config.py:106 |
| A non-finite simulation sets terminated and reaching the horizon sets truncated | upstream_code | gym_softrobot/envs/octopus/muscle_crawl_env.py:111-112 |
| reset(seed) seeds the environment random generator and returns the observation with an info dict that reports time | upstream_code | gym_softrobot/envs/octopus/muscle_crawl_env.py:87-95 |
| The simulation uses the Position Verlet integrator | upstream_code | gym_softrobot/envs/octopus/crawling_simulation/phase_simulation.py:123 |
| The default physics timestep is 3.0e-4 s | upstream_code | gym_softrobot/envs/octopus/crawling_simulation/config.py:94 |
| The robot is a rigid central sphere of radius 0.09 m with arms of length 0.45 m, base radius 0.02 m and 15 elements | upstream_code | gym_softrobot/envs/octopus/crawling_simulation/config.py:28-33 |
| Gravity acts in the negative y direction with -9.80665 m/s^2 | upstream_code | gym_softrobot/envs/octopus/crawling_simulation/config.py:53 |
| Rod-rod contact is disabled by default | upstream_code | gym_softrobot/envs/octopus/crawling_simulation/config.py:87 |
| The environment supports an rgb_array render mode | upstream_code | gym_softrobot/envs/octopus/muscle_crawl_env.py:33 |

Limits: the driver declares none. The action bound comes from the environment's `Box(-1, 1, shape=(8, 9))` and is
derived by the Gymnasium bridge; `ticks` is bounded by the bridge's `max_ticks` (10000). The device is simulated (R0),
so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:OctoMuscleCrawl-v0`, level F0 (the deployed
fake is a kinematic point-mass surrogate, not the upstream Cosserat-rod simulation), determinism `seeded` with
`seed_control` `parameter`, timestep 1000/60 ms (`control_dt = 1/60` s, config.py:95), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled and that the fake was not
compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step,
reset or seed is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the
last observation stays readable.

Tags: octopus, soft-robot, cosserat, crawling, reinforcement-learning, simulation, gymnasium
