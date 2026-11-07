# Facts and tags for gh.mattchantk/gym-maze

Every fact cites its source at commit `83176811b49b5538a6213520612f44fb1bc49114`; the same facts are
written into `driver.py` (`facts = [...]`). The reference file is generated from the driver, not from
this page.

| fact | source | ref |
|---|---|---|
| MazeEnvSample5x5 loads the pre-generated maze file maze2d_5x5.npy, a 5x5 world | upstream_code | gym_maze/envs/maze_env.py:111-112 |
| The action space is Discrete(2*len(maze_size)), so the 5x5 sample maze has four integer actions | upstream_code | gym_maze/envs/maze_env.py:44 |
| ACTION lists the four directions N, S, E, W | upstream_code | gym_maze/envs/maze_env.py:14 |
| An integer action is an index into ACTION; step calls move_robot with that direction | upstream_code | gym_maze/envs/maze_env.py:73-77 |
| If the destination is blocked, move_robot does not move the robot | upstream_code | gym_maze/envs/maze_view_2d.py:97-103 |
| is_open requires the destination to be inside the grid and allows the move when either side of the shared wall is open | upstream_code | gym_maze/envs/maze_view_2d.py:442-453 |
| The observation space is a two-element Box of integers from 0 to maze_size-1 | upstream_code | gym_maze/envs/maze_env.py:46-49 |
| The entrance is cell (0, 0) and the goal is the last cell, maze_size - (1, 1) | upstream_code | gym_maze/envs/maze_view_2d.py:39-43 |
| reset puts the robot back at the entrance, sets state to zeros(2), clears steps_beyond_done, sets done False and returns the state | upstream_code | gym_maze/envs/maze_env.py:92-97 |
| A step gives reward 1 and done True at the goal, otherwise reward -0.1/(maze_size[0]*maze_size[1]) and done False | upstream_code | gym_maze/envs/maze_env.py:79-84 |
| step returns the legacy four-tuple (state, reward, done, info) and has no truncated flag | upstream_code | gym_maze/envs/maze_env.py:88-90 |
| MazeEnv.seed seeds a numpy random generator and returns [seed] | upstream_code | gym_maze/envs/maze_env.py:69-71 |
| reset takes no arguments and returns the fixed zero state; it does not draw from the generator set by seed | upstream_code | gym_maze/envs/maze_env.py:92-97 |
| step moves the robot on the fixed maze data and does not draw from a random generator | upstream_code | gym_maze/envs/maze_env.py:73-90 |
| maze-v0 is registered to MazeEnvSample5x5 with max_episode_steps=2000 | upstream_code | gym_maze/__init__.py:4-8 |
| The upstream package declares gym, pygame and numpy as install requirements | upstream_code | setup.py:12 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the
environment (`Discrete(4)`: `action.index` from 0 to 3, with no source and the reference
`action_space of the fake backend .fake:FakeMazeEnvSample5x5`). The device is simulated (R0), so no
limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gym_maze:maze-v0`, level F0 (a kinematic
grid transition, no physics and no continuous time, so `timestep_ms` is 0 and the model is event
driven), determinism `exact` with `seed_control` `none` (the fixed sample maze does not draw from the
generator that `MazeEnv.seed` installs; the bridge's state hash also counts the episode, so two runs
compare from a fresh world or the same episode ordinal), `realtime_factor` 0, clock `lockstep`, reset
`full`, no snapshot and restore. The gaps say what is not modelled: physics, wall-clock pacing, the
pygame viewer and the rgb_array image, the raw class's four-tuple step versus the fake's emulation of
the registered 2000-step TimeLimit, the random/portal/loop variants, and that the fake was never
compared with a run of the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (there is no native stop); after
it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays
readable.

Tags: maze, grid-world, reinforcement-learning, simulation, gym
