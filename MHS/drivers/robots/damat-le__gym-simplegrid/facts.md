# Facts and tags for gh.damat-le/gym-simplegrid

Every fact cites its source at commit `6ded2fcf684727b27b5569688cad6f92bc3bc52b`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| MOVES maps action 0 to up, 1 to down, 2 to left and 3 to right, and the action space is Discrete(4) | upstream_code | gym_simplegrid/envs/simple_grid.py:22-42 |
| The observation space is Discrete(nrow * ncol), one integer per grid cell | upstream_code | gym_simplegrid/envs/simple_grid.py:43 |
| An observation is the flattened cell index row * ncol + col | upstream_code | gym_simplegrid/grid.py:89 |
| A grid cell is free when it holds 0 and an obstacle when it holds 1 | upstream_code | gym_simplegrid/grid.py:28-29 |
| GridModel.is_free returns False for a cell outside the grid | upstream_code | gym_simplegrid/grid.py:69-71 |
| A step moves the agent to the target cell when it is in bounds and free, and leaves it in place otherwise | upstream_code | gym_simplegrid/envs/simple_grid.py:90-96 |
| The reward is +1.0 on the goal, -0.1 for a valid non-goal cell and -1.0 for an invalid move | upstream_code | gym_simplegrid/envs/simple_grid.py:140-144 |
| The episode terminates when the agent reaches the goal | upstream_code | gym_simplegrid/envs/simple_grid.py:105 |
| The episode truncates when step_count is at least max_steps and the goal was not reached on that step | upstream_code | gym_simplegrid/envs/simple_grid.py:108-112 |
| step returns (observation, reward, terminated, truncated, info) | upstream_code | gym_simplegrid/envs/simple_grid.py:114 |
| The reset info carries agent_xy and step_count | upstream_code | gym_simplegrid/envs/simple_grid.py:149-150 |
| reset(seed) calls super().reset(seed=seed), so the sampled positions come from the environment's numpy generator | upstream_code | gym_simplegrid/envs/simple_grid.py:68 |
| A reset without a start_loc or goal_loc option samples a free cell with GridModel.sample_valid_xy | upstream_code | gym_simplegrid/envs/simple_grid.py:167-168 |
| The start_loc and goal_loc options accept a flat integer index or a (row, col) pair, and an invalid start or goal raises ValueError | upstream_code | gym_simplegrid/envs/simple_grid.py:158-174 |
| SimpleGrid-4x4-v0 is registered with entry point gym_simplegrid.envs:SimpleGridEnv, kwargs obstacle_map=MAP_4x4 and max_episode_steps=200 | upstream_code | gym_simplegrid/__init__.py:28-33 |
| MAP_4x4 has four rows of four cells: 0000, 0101, 0001 and 1000 | upstream_code | gym_simplegrid/__init__.py:5 |
| The environment declares the render modes human, rgb_array and ansi with render_fps 8 | upstream_code | gym_simplegrid/envs/simple_grid.py:20 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Discrete(4)`: `action.index` from 0 to 3, with no source and the ref
`action_space of the fake backend .fake:FakeSimpleGridEnv`), and `ticks` (1 to `max_ticks`, 10000 by default). The
device is simulated (R0), so no limit is `operator_required`.

Configuration: `env_id = "SimpleGrid-4x4-v0"` is the pre-registered environment whose registration supplies the
`obstacle_map` that the generic `SimpleGrid-v0` requires (`gym_simplegrid/__init__.py:20-33`). `env_kwargs` is empty.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:SimpleGrid-4x4-v0`, level F0 (a discrete grid
state machine with no dynamics, contact, actuator, sensor or noise model), determinism `seeded` with `seed_control`
`parameter` (`simple_grid.py:68` and `:167-168`), timestep 0 ms with a note that the environment has no time base,
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled and
that this package's fake was not compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: simplegrid, grid-world, navigation, reinforcement-learning, simulation, gymnasium
