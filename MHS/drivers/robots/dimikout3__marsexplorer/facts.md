# Facts and tags for gh.dimikout3/marsexplorer

Every fact cites its source at commit `6533a9a05bde1050bc639ee40096240680ad6f2d`, relative to the clone root
`robots/dimikout3/marsexplorer`. The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The gym environment explorer-v01 is registered with entry point mars_explorer.envs:Explorer | upstream_code | mars-explorer/mars_explorer/__init__.py:3-5 |
| The action space is Discrete(4): four integer actions 0, 1, 2 and 3 | upstream_code | mars-explorer/mars_explorer/envs/explorer.py:32 |
| The observation space is a Box with minimum 0 and maximum 1 | upstream_code | mars-explorer/mars_explorer/envs/explorer.py:33 |
| The default map is 21 by 21 cells | upstream_code | mars-explorer/mars_explorer/envs/settings.py:5 |
| Action 0 moves one cell on the first axis, action 1 the opposite way, action 2 one cell on the second axis and action 3 the opposite way | upstream_code | mars-explorer/mars_explorer/envs/explorer.py:111-120 |
| A move outside the map sets out_of_bounds and a move into an obstacle sets collision | upstream_code | mars-explorer/mars_explorer/envs/explorer.py:128-141 |
| The step reward is the number of newly explored cells minus the movement cost | upstream_code | mars-explorer/mars_explorer/envs/explorer.py:178-182 |
| The default movement cost is 0.2 | upstream_code | mars-explorer/mars_explorer/envs/settings.py:7 |
| The episode ends when timeStep is greater than max_steps | upstream_code | mars-explorer/mars_explorer/envs/explorer.py:187 |
| The default max_steps is 400 | upstream_code | mars-explorer/mars_explorer/envs/settings.py:25 |
| The episode ends with bonus_reward when more than 95 percent of the map is explored | upstream_code | mars-explorer/mars_explorer/envs/explorer.py:189-191 |
| The default bonus_reward is 400 | upstream_code | mars-explorer/mars_explorer/envs/settings.py:26 |
| A collision or an out-of-bounds move ends the episode with collision_reward or out_of_bounds_reward | upstream_code | mars-explorer/mars_explorer/envs/explorer.py:192-197 |
| The default collision_reward and out_of_bounds_reward are -400 | upstream_code | mars-explorer/mars_explorer/envs/settings.py:27-28 |
| The lidar scans 32 channels with a range of 6 cells | upstream_code | mars-explorer/mars_explorer/envs/settings.py:31-32 |
| The default initial position is [0, 0] | upstream_code | mars-explorer/mars_explorer/envs/settings.py:4 |
| The default configuration places 12 obstacles with margins [1, 1] and obstacle size [2, 2] | upstream_code | mars-explorer/mars_explorer/envs/settings.py:12-23 |
| reset() takes no arguments and returns the initial observation | upstream_code | mars-explorer/mars_explorer/envs/explorer.py:38-92 |
| step() returns the legacy four-tuple (observation, reward, done, info) | upstream_code | mars-explorer/mars_explorer/envs/explorer.py:207-216 |
| reset() has no seed parameter and the class defines no seed() method | upstream_code | mars-explorer/mars_explorer/envs/explorer.py:38 |
| Obstacle positions are drawn with numpy's global random generator (np.random.randint) | upstream_code | mars-explorer/mars_explorer/utils/randomMapGenerator.py:71-72 |
| The lidar resolution default is 200 samples | upstream_code | mars-explorer/mars_explorer/utils/lidarSensor.py:6-7 |

Limits: the driver declares none. The only bound is the action space, which the Gymnasium bridge derives from
`Discrete(4)` (`action.index` from 0 to 3, source `upstream_code`, ref
`mars-explorer/mars_explorer/envs/explorer.py:32`), and `ticks` (1 to `max_ticks`, 10000 by
default). The device is simulated (R0), so no limit is `operator_required` and there is no site-limits overlay.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gym:explorer-v01`, level F0 (a kinematic grid world, no
dynamics), determinism `none` because the map comes from numpy's global generator and `reset()` takes no seed,
`timestep_ms` 0 (an event-driven analytic model), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The gaps say what is not modelled, that the fake was not compared with upstream, that the observation is
flattened to 441 numbers, and that rendering is not bound.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the last
observation stays readable. The bridge's `autoreset` is on: a step after a terminal state starts the next episode
(the upstream environment ends an episode at `explorer.py:185-197`; the wrapper resets before the next action).

Tags: mars, exploration, grid-world, lidar, reinforcement-learning, simulation, gym
