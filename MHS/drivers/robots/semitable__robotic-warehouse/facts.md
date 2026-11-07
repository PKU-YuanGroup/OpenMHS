# Facts and tags for gh.semitable/robotic-warehouse

Every fact cites its source at commit `96fbc64e3eae5fee915e0d390f864fa06ddccd47`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The normal registration loop registers rware-{size}-{agents}ag{diff}-v2 with entry_point rware.warehouse:Warehouse for the tiny, small, medium and large layouts, the default, easy and hard difficulties and 1 to 19 agents; for tiny, 1 agent and the default difficulty the id is rware-tiny-1ag-v2 | upstream_code | rware/__init__.py:7-39 |
| The registered tiny layout uses column_height 8, shelf_rows 1, shelf_columns 3, n_agents 1, msg_bits 0, sensor_range 1, request_queue_size 1, max_inactivity_steps None, max_steps 500 and individual rewards | upstream_code | rware/__init__.py:27-38 |
| The Action enum has five actions: NOOP=0, FORWARD=1, LEFT=2, RIGHT=3 and TOGGLE_LOAD=4 | upstream_code | rware/warehouse.py:31-36 |
| The action space is a Tuple with one Discrete(len(Action)) per agent, which is a Tuple of one Discrete(5) for the registered one-agent layout | upstream_code | rware/warehouse.py:255-260 |
| The Direction enum has four values: UP=0, DOWN=1, LEFT=2 and RIGHT=3 | upstream_code | rware/warehouse.py:39-44 |
| The default observation space is built by _use_fast_obs: it flattens each per-agent sub-space of the slow observation space into a Box and returns a Tuple with one Box per agent | upstream_code | rware/warehouse.py:505-522 |
| The sensor window of an agent has (1 + 2 * sensor_range) ** 2 cells, which is a 3x3 window at the registered sensor_range 1 | upstream_code | rware/warehouse.py:432-437 |
| The grid height is (column_height + 1) * shelf_rows + 2 and its width is (2 + 1) * shelf_columns + 1; the goals are the two cells in the middle of the last row | upstream_code | rware/warehouse.py:294-306 |
| A reset recreates the shelves, spawns the agents at random grid locations with random directions and samples the request queue from the shelves using np_random | upstream_code | rware/warehouse.py:757-799 |
| step maps each tuple element to an Action and a forward move of an agent carrying a shelf into a standing shelf is cancelled to NOOP | upstream_code | rware/warehouse.py:804-844 |
| A requested shelf delivered to a goal is replaced in the request queue by a uniformly sampled shelf that is not currently requested | upstream_code | rware/warehouse.py:905-918 |
| With RewardType.INDIVIDUAL the agent that delivers a requested shelf to a goal receives +1 | upstream_code | rware/warehouse.py:919-924 |
| The episode reports done when max_inactivity_steps or max_steps is reached; truncated is always False | upstream_code | rware/warehouse.py:936-942 |
| The environment metadata declares the render modes human and rgb_array at 10 frames per second | upstream_code | rware/warehouse.py:141-143 |

Limits: the driver declares none. This is a simulated R0 device. The action space is a Tuple of one
`Discrete(5)` per agent; the Gymnasium bridge publishes a Tuple's structure but no per-element bounds (the bridge
docstring calls this a simulation-only residual), so the fake validates the action itself and an action outside
0..4 fails instead of being refused with `MHS.SAFETY.ENVELOPE_VIOLATION`. The `ticks` input keeps the bridge's
schema bound 1..10000. No bound is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:rware-tiny-1ag-v2`, level F0 (a discrete grid
world with no continuous dynamics), determinism `seeded` with `seed_control` `parameter`, timestep 0 (the
environment has no physical timestep; one tick is one discrete transition), `realtime_factor` 0, clock `lockstep`,
reset `full`, no snapshot and restore. The gaps say what is not modelled, that the fake returns the one-agent scalar
reward where upstream returns a per-agent list, and that the fake was not compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (the environment has no native stop); after
it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: rware, warehouse, multi-robot, reinforcement-learning, simulation, gymnasium
