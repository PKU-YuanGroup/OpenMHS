# Facts and tags for gh.erfanmhi/deep-reinforcement-learning-cs285-pytorch

Every fact cites its source at commit `6da04f367e52a451c202ae7e5477994c1d149baf`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The environment is registered as obstacles-cs285-v0 with max_episode_steps=500 | upstream_code | hw4/cs285/envs/obstacles/__init__.py:3-7 |
| The action dimension is 2 and the observation dimension is 4 | upstream_code | hw4/cs285/envs/obstacles/obstacles_env.py:11-12 |
| The action space is a Box of 2 elements bounded by boundary_min -0.99 and boundary_max 0.99 | upstream_code | hw4/cs285/envs/obstacles/obstacles_env.py:13-18 |
| The observation space is a Box of 4 elements bounded by -inf and inf | upstream_code | hw4/cs285/envs/obstacles/obstacles_env.py:20-22 |
| The constructor defaults are start [-0.5, 0.75], end [0.7, -0.8] and random_starts True | upstream_code | hw4/cs285/envs/obstacles/obstacles_env.py:6 |
| The five obstacles are axis-aligned rectangles [x of top left, y of top left, width x, height y] | upstream_code | hw4/cs285/envs/obstacles/obstacles_env.py:32-38 |
| seed(seed) seeds numpy's global random generator | upstream_code | hw4/cs285/envs/obstacles/obstacles_env.py:43-44 |
| With random_starts, reset draws x uniformly between boundary_min and boundary_min+1.25 and y between boundary_max-0.4 and boundary_max, and re-draws while the point is invalid | upstream_code | hw4/cs285/envs/obstacles/obstacles_env.py:48-55 |
| reset sets current to the drawn start and end to the configured end, clears the counter and returns the observation | upstream_code | hw4/cs285/envs/obstacles/obstacles_env.py:59-78 |
| The observation is [current x, current y, end x, end y] | upstream_code | hw4/cs285/envs/obstacles/obstacles_env.py:82-83 |
| The score is the negation of the absolute current-to-end difference per axis | upstream_code | hw4/cs285/envs/obstacles/obstacles_env.py:85-89 |
| The done threshold is eps 0.1 | upstream_code | hw4/cs285/envs/obstacles/obstacles_env.py:40 |
| The reward is minus the Euclidean distance between current and end; done is 1 when the distance is below eps or the current position is out of the boundary | upstream_code | hw4/cs285/envs/obstacles/obstacles_env.py:114-132 |
| step increments the counter, clips the action to [-1, 1], scales it by 0.1, and moves current only when the new point is valid | upstream_code | hw4/cs285/envs/obstacles/obstacles_env.py:139-147 |
| step returns (observation, reward, done, info) and has no truncated flag | upstream_code | hw4/cs285/envs/obstacles/obstacles_env.py:149-156 |
| render returns a matplotlib RGB image of the boundaries, obstacles, current position and end | upstream_code | hw4/cs285/envs/obstacles/obstacles_env.py:162-192 |
| A point is valid when it is strictly inside the boundary on both axes and not strictly inside any obstacle rectangle | upstream_code | hw4/cs285/envs/obstacles/obstacles_env.py:194-225 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box` of two elements, -0.99 to 0.99, with no source and the ref
`action_space of the fake backend .fake:FakeObstacles`), plus `ticks` (1 to `max_ticks`, 10000 by default). The
device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:cs285.envs.obstacles`, level F0 (kinematic
navigation, no forces or contacts), determinism `seeded` with `seed_control` `parameter`, timestep 0 (event-driven,
`ticks` count discrete moves), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps
say what is not modelled (including the 500-step gym TimeLimit and the render image array) and that this package's
fake was not compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step,
seed or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: obstacles, navigation, reinforcement-learning, simulation, gymnasium
