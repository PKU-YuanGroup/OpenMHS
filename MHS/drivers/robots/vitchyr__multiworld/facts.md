# Facts and tags for gh.vitchyr/multiworld

Every fact cites its source at commit `12a05bfa4139f90741608ba409edebb95d7ef9ab`. The same facts are written into
`driver.py` (`facts = [...]`); the reference files are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The ACTIONS list defines five actions, in order (-1, 0), (0, 1), (1, 0), (0, -1) and (0, 0) | upstream_code | multiworld/envs/gridworlds/goal_gridworld.py:13 |
| The action space is Discrete(nA), where nA is the length of the ACTIONS list | upstream_code | multiworld/envs/gridworlds/goal_gridworld.py:39-45 |
| GoalGridworld-v0 is registered with entry point multiworld.envs.gridworlds.goal_gridworld:GoalGridworld and no keyword arguments | upstream_code | multiworld/envs/gridworlds/__init__.py:2-5 |
| The constructor's default grid is 10 rows by 10 columns | upstream_code | multiworld/envs/gridworlds/goal_gridworld.py:35-36 |
| The observation space is a Dict with the members observation, achieved_goal and desired_goal; each member is a Box of shape (rows, columns, 1) with low 0 and high 1 | upstream_code | multiworld/envs/gridworlds/goal_gridworld.py:46-49 |
| A reset draws the agent cell and the goal cell from one random permutation of all grid cells, so the two cells are distinct, and starts the step count at 0 | upstream_code | multiworld/envs/gridworlds/goal_gridworld.py:69-76 |
| move_agent adds the action's offset to the agent row and column and keeps the old cell when the move would leave the grid | upstream_code | multiworld/envs/gridworlds/goal_gridworld.py:88-102 |
| An episode ends after 41 steps: the step count is incremented and done becomes true when the count is greater than 40 | upstream_code | multiworld/envs/gridworlds/goal_gridworld.py:104-115 |
| The reward is the negative sum of squared differences between the achieved and desired flattened observations | upstream_code | multiworld/envs/gridworlds/goal_gridworld.py:176-177 |
| The achieved observation image is 1 at the agent cell and 0.2 at each in-bounds diagonal neighbour | upstream_code | multiworld/envs/gridworlds/goal_gridworld.py:128-138 |
| The desired observation image is 0.2 at every in-bounds cell of the goal's 3 x 3 neighbourhood and 1 at the goal cell itself | upstream_code | multiworld/envs/gridworlds/goal_gridworld.py:140-151 |
| The step info carries success 0, the step count and the done flag | upstream_code | multiworld/envs/gridworlds/goal_gridworld.py:113-125 |

## Limits

The driver declares no limit of its own. The only device bounds are derived by the Gymnasium bridge from the
environment itself: `action.index` is bounded from 0 to 4 by `spaces.Discrete(5)` (`goal_gridworld.py:45`), and
`ticks` is bounded by the family's `max_ticks` setting, which is a runtime configuration rather than a property of
this environment. The device is simulated at R0, so no limit is `operator_required`.

## Fidelity contract

`driver.py` publishes engine `custom:multiworld:GoalGridworld-v0`, level F0 (kinematic/analytic: one tick is one
move on a grid, no dynamics), determinism `seeded` with `seed_control` `parameter`, `timestep_ms` 0 (event-driven
model), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot/restore. The `gaps` say that the fake uses
Python's `random.Random` while upstream's `reset()` draws from the unseeded global numpy generator, that no
rendering is offered, and that the fake was not compared with the upstream environment.

## Entry symbols

This package implements one device class, the card's first confirmed entry symbol,
`multiworld.envs.gridworlds.goal_gridworld:GoalGridworld` (the `GoalGridworld-v0` registration). The card's other
entry symbols are MuJoCo Sawyer environments and are not covered here:

- `multiworld.envs.mujoco.sawyer_xyz.sawyer_push_nips:SawyerPushAndReachXYEasyEnv`
  (`multiworld/envs/mujoco/sawyer_xyz/sawyer_push_nips.py:511`)
- `multiworld.envs.mujoco.sawyer_xyz.sawyer_door_hook:SawyerDoorHookEnv`
  (`multiworld/envs/mujoco/sawyer_xyz/sawyer_door_hook.py:19`)
- `multiworld.envs.mujoco.sawyer_xyz.sawyer_pick_and_place:SawyerPickAndPlaceEnvYZ`
  (`multiworld/envs/mujoco/sawyer_xyz/sawyer_pick_and_place.py:434`)
- `multiworld.envs.mujoco.sawyer_xyz.sawyer_reach:SawyerReachXYEnv`
  (`multiworld/envs/mujoco/sawyer_xyz/sawyer_reach.py:222`)

They need `mujoco-py` and the MuJoCo 2.1 binaries (the card's `install.system_deps`) and are actuated robot arms,
not the selected grid world. The card's `models` list is the MuJoCo XML scene set for those environments and is not
used by this package.

## Safety

Simulated R0 device. There is no hardware backend, no actuator and no physical stop path. An e-stop is the
runtime's software latch: after it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the
grid state stays readable.

## Tags

multiworld, goal-gridworld, gridworld, goal-conditioned, reinforcement-learning, simulation, gym
