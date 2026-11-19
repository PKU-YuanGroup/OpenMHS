# Facts and tags for gh.chirikjianlab/ravens_visual_foresight

Every fact cites its source at commit `9d3c95555d420c086f465dc11bcb2758cf05247a`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Environment is a gym.Env subclass and its docstring calls it an OpenAI Gym-style environment class | upstream_code | ravens/environments/environment.py:42-43 |
| The constructor's default control frequency is hz=240 and p.setTimeStep(1. / hz) sets the simulation timestep from it | upstream_code | ravens/environments/environment.py:50-138 |
| The action space is a Dict with pose0 and pose1; each is a Tuple of a 3-vector position bounded low [0.25, -0.5, 0.] and high [0.75, 0.5, 0.28] and a 4-vector orientation bounded -1.0 to 1.0 | upstream_code | ravens/environments/environment.py:89-102 |
| The observation space is a Dict of color and depth Tuples, one entry per camera; color is 0..255 uint8 and depth is 0.0..20.0 float32 | upstream_code | ravens/environments/environment.py:77-88 |
| The environment uses three RealSense D415 cameras declared with image_size (480, 640) | upstream_code | ravens/tasks/cameras.py:22-26 |
| EnvironmentMCTS.step treats pose0 as the PICK pose and pose1 as the PLACE pose and returns [pick_obs, place_obs], reward, done, info | upstream_code | ravens/environments/environment_mcts.py:58-116 |
| EnvironmentMCTS.reset resets the task, calls step() with no action, and returns the 6-tuple (init_obs, base_urdf, base_size, base_id, objs_id, info) | upstream_code | ravens/environments/environment_mcts.py:159-166 |
| demos_tvf.py defaults --task to put-block-base, builds tasks.names[task + '-mcts'], and runs EnvironmentMCTS with hz=480 | upstream_code | ravens/demos_tvf.py:12-33 |
| The task registry maps 'put-block-base-mcts' to PutBlockBaseMCTS | upstream_code | ravens/tasks/__init__.py:70 |
| PutBlockBaseMCTS has 3 blocks, a stand base of size (0.05, 0.15, 0.005), three place positions on the base, and max_steps = num_blocks + 2 | upstream_code | ravens/tasks/put_block_base_mcts.py:27-57 |
| PutBlockBaseMCTS appends one goal with its object list and max_reward 1 | upstream_code | ravens/tasks/put_block_base_mcts.py:81-82 |
| TaskMCTS.reward adds max_reward / len(objs) to step_reward | upstream_code | ravens/tasks/task_mcts.py:240 |
| TaskMCTS.done returns true when no goals remain or the accumulated reward exceeds 0.99 | upstream_code | ravens/tasks/task_mcts.py:316 |
| Environment.seed sets a numpy RandomState for the environment's random generator and returns the seed | upstream_code | ravens/environments/environment.py:175-177 |
| The reset loads a UR5 arm with a suction end effector and moves its joints to the home configuration | upstream_code | ravens/environments/environment_mcts.py:140-154 |
| The put-block-base task's workspace bounds are x 0.25..0.75, y -0.25..0.25 and z 0..0.28 | upstream_code | ravens/tasks/put_block_base_mcts.py:44 |
| The task sets block_size to (0.04, 0.04, 0.04) | upstream_code | ravens/tasks/put_block_base_mcts.py:25 |

Limits: `adapter.py` preserves the native `Dict(Tuple(Box, Box))` action and supplies numeric schemas for
both positions (3 values) and quaternions (4 values). It derives the per-coordinate bounds from the exact native
spaces cited by `action_space_ref` at environment.py:89-102. Both pose0 and pose1 are checked before dispatch;
malformed tuple members are input errors and values outside the source bounds are envelope violations. R0 does
not waive the input envelope. The adapter uses public GymnasiumBridge schema/limit hooks; no SDK file changed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic`, level F0 (kinematic, no dynamics), determinism
`seeded` with `seed_control` `parameter`, timestep 1000/240 ms from the default `hz=240` (environment.py:50 and :138),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled: no
physics, contacts, suction or arm, one task only, an 8x8 placeholder image instead of 480x640 RGB-D, Python RNG
instead of numpy, the dropped reset 6-tuple fields, the unhonoured reset options, and the base action-space y range.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: ravens, visual-foresight, pick-place, rearrangement, pybullet, simulation, gymnasium
