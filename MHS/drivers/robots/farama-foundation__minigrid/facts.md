# Facts and tags for gh.farama-foundation/minigrid

This card is a driver pack: the repository holds one environment class per file and the card lists five entry symbols.
One package covers one simulator, so this package covers the first entry symbol of the card,
`minigrid.envs:BlockedUnlockPickupEnv` (`minigrid/envs/blockedunlockpickup.py:9`), registered as
MiniGrid-BlockedUnlockPickup-v0.

Every fact cites its source at commit `b34a5755dbef71e3f1662552259a94b255c1a8bb`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| BlockedUnlockPickupEnv is registered as MiniGrid-BlockedUnlockPickup-v0 with the entry point minigrid.envs:BlockedUnlockPickupEnv | upstream_code | minigrid/__init__.py:17-20 |
| The seven actions are left 0, right 1, forward 2, pickup 3, drop 4, toggle 5 and done 6 | upstream_code | minigrid/core/actions.py:6-20 |
| The action space is Discrete(len(actions)), i.e. Discrete(7) | upstream_code | minigrid/minigrid_env.py:63 |
| The observation space is a Dict of image = Box(low=0, high=255, shape=(agent_view_size, agent_view_size, 3), dtype=uint8), direction = Discrete(4) and the mission space | upstream_code | minigrid/minigrid_env.py:72-83 |
| agent_view_size defaults to 7 | upstream_code | minigrid/minigrid_env.py:42 |
| The direction is 0 right, 1 down, 2 left, 3 up (DIR_TO_VEC), and the direction string map is '>', 'V', '<', '^' | upstream_code | minigrid/core/constants.py:48-57 |
| Each tile is encoded as (OBJECT_IDX, COLOR_IDX, STATE) and the door STATE is 0 open, 1 closed, 2 locked | upstream_code | minigrid/envs/blockedunlockpickup.py:41-47 |
| OBJECT_TO_IDX maps unseen 0, empty 1, wall 2, floor 3, door 4, key 5, ball 6, box 7, goal 8, lava 9, agent 10; COLOR_TO_IDX maps red 0, green 1, blue 2, purple 3, yellow 4, grey 5 | upstream_code | minigrid/core/constants.py:20-37 |
| step increments step_count and then branches on the action: left decrements the direction, right increments it, forward moves when the front cell is empty or can be overlapped, pickup and drop move an object, toggle activates the front cell, and the done action does nothing | upstream_code | minigrid/minigrid_env.py:525-582 |
| The episode is truncated when step_count reaches max_steps | upstream_code | minigrid/minigrid_env.py:587-588 |
| The success reward is 1 - 0.9 * (step_count / max_steps) | upstream_code | minigrid/minigrid_env.py:245 |
| BlockedUnlockPickupEnv ends the episode when the agent picks up the target box, with the success reward | upstream_code | minigrid/envs/blockedunlockpickup.py:107-115 |
| The room grid is (room_size - 1) * num_rows + 1 high and (room_size - 1) * num_cols + 1 wide | upstream_code | minigrid/core/roomgrid.py:89-90 |
| BlockedUnlockPickupEnv uses two rooms of size 6 (num_rows 1, num_cols 2, so a 6 x 11 grid) and max_steps = 16 * room_size**2 when it is not given | upstream_code | minigrid/envs/blockedunlockpickup.py:72-83 |
| The generated grid puts a box in the right room, a locked door between the rooms, a ball that blocks the door, a key in the left room and the agent in the left room | upstream_code | minigrid/envs/blockedunlockpickup.py:89-105 |

Limits: the only bounded input is the action index, and the bridge derives it from the environment's action space
`Discrete(7)` (0 to 6) at load time; the driver declares no limit of its own and the simulated R0 driver needs none.

Safety: a simulated R0 environment has no machine to stop. An e-stop stops the simulation from advancing: no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the world state stays readable.

Mock path: the card's `mock_strategy.preferred` is `upstream-sim`, but the gate cannot import the upstream (the clone
needs numpy, gymnasium and pygame-ce, `pyproject.toml:32`), so the `fake` backend is the package's own pure Python
world (`fake.py`). A backend name that `backends` does not list (`sim`) would be served by
`gymnasium.make("MiniGrid-BlockedUnlockPickup-v0")`; that path was not run here.

Not covered by this package (driver pack, one environment per package):

- `minigrid.envs:CrossingEnv` (`minigrid/envs/crossing.py:13`), the lava and simple crossing environments;
- `minigrid.envs:DistShiftEnv` (`minigrid/envs/distshift.py:9`), the distribution-shift environment;
- `minigrid.envs:DoorKeyEnv` (`minigrid/envs/doorkey.py:9`), the door-and-key environment;
- `minigrid.envs:DynamicObstaclesEnv` (`minigrid/envs/dynamicobstacles.py:13`), the moving-obstacles environment.
- Inside the covered environment the fake does not model occlusion of the agent's view (the whole 7 x 7 window is
  visible), a freshly generated RoomGrid layout (the layout is the fixed two-room arrangement of the upstream
  generator), the rendering, or `get_state`/`set_state` (the clone has none), and its colours come from Python's
  `random.Random` rather than numpy's generator; see the fidelity `gaps` of `driver.py`.

Tags: minigrid, gridworld, reinforcement-learning, simulation, gymnasium
