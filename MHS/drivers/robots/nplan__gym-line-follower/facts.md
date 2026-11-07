# Facts and tags for gh.nplan/gym-line-follower

Every fact cites its source at commit `11b3dd8fe791c02bc36cbbf91c686825776b3025`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The package registers LineFollower-v0 (entry point gym_line_follower.envs:LineFollowerEnv) and LineFollowerCamera-v0 (entry point gym_line_follower.envs:LineFollowerCameraEnv) | upstream_code | gym_line_follower/__init__.py:3-12 |
| The action space is a Box of two motor-power values with low -1.0 and high 1.0 | upstream_code | gym_line_follower/envs/line_follower_env.py:80 |
| The constructor defaults are gui=True, nb_cam_pts=8, sub_steps=10, sim_time_step=1/250 s, max_track_err=0.3, power_limit=0.4 and max_time=60 s | upstream_code | gym_line_follower/envs/line_follower_env.py:31-33 |
| The default observation type is points_latch | upstream_code | gym_line_follower/envs/line_follower_env.py:31-32 |
| The points_latch observation space is 2*nb_cam_pts values, with x in [0.0, 0.3] and y in [-0.2, 0.2] for each point | upstream_code | gym_line_follower/envs/line_follower_env.py:89-92 |
| A step scales every action by self.speed_limit before applying it | upstream_code | gym_line_follower/envs/line_follower_env.py:171-172 |
| self.speed_limit is the power_limit constructor argument | upstream_code | gym_line_follower/envs/line_follower_env.py:71 |
| One environment step runs sub_steps simulation steps and then reads the follower bot position | upstream_code | gym_line_follower/envs/line_follower_env.py:179-184 |
| With the constructor defaults sub_steps=10 and sim_time_step=1/250 s, one environment step advances 0.04 s of simulated time | upstream_code | gym_line_follower/envs/line_follower_env.py:31-32 |
| A reset generates a track and, when randomize is true, adds a start-yaw offset drawn uniformly from (-0.2, 0.2) rad | upstream_code | gym_line_follower/envs/line_follower_env.py:142-147 |
| The reward is -0.2 per step plus 1000/nb_checkpoints * (1 - track_err/max_track_err)^2 for every checkpoint reached | upstream_code | gym_line_follower/envs/line_follower_env.py:211-218 |
| The episode ends when the track is done, the progress deviates by more than 0.5, the track error exceeds max_track_err, or the step counter exceeds max_steps; a failed episode gets reward -100 | upstream_code | gym_line_follower/envs/line_follower_env.py:220-234 |
| seed() uses gym.utils.seeding.np_random and returns the seed as a one-element list | upstream_code | gym_line_follower/envs/line_follower_env.py:323-325 |
| LineFollowerCameraEnv subclasses LineFollowerEnv and forces obsv_type='camera' | upstream_code | gym_line_follower/envs/line_follower_env.py:342-345 |
| The camera observation space is a 240 x 320 x 3 uint8 image | upstream_code | gym_line_follower/envs/line_follower_env.py:101-102 |
| The observation is 8 line points as x, y pairs in the robot's coordinate frame, with x in (0, 0.3) and y in (-0.2, 0.2) | vendor_doc | README.md:74-77 |
| The follower starts at the beginning of a closed-loop track and the episode ends when the loop is complete or the follower leaves the line | vendor_doc | README.md:63-67 |

Limits: the driver declares none. The only bound on an input is the action space, which the bridge derives from the
environment's two-element Box (no source, ref `action_space of the fake backend .fake:FakeLineFollowerEnv`), plus
`ticks` (1 to `max_ticks`, 10000 by default). The device is simulated (R0), so no limit is `operator_required`. The
constructor defaults above (power limit, maximum track error, maximum time) are configuration of the upstream
environment, not bounds the driver may impose; a deployment can pass different constructor values to `LineFollowerEnv`,
so they are written as facts about the defaults only.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:line-follower-kinematics`, level F0 (kinematic
unicycle, no rigid-body dynamics, contacts, motor, sensor or noise model), determinism `seeded` with `seed_control`
`parameter`, timestep 40 ms (`sub_steps = 10` times `sim_time_step = 1/250` s), `realtime_factor` 0, clock `lockstep`,
reset `full`, no snapshot and restore. The gaps say what is not modelled, that the fake track is a fixed circle rather
than the randomised Bezier loop, and that the fake was not compared with the upstream PyBullet environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: line-follower, differential-drive, reinforcement-learning, simulation, gym
