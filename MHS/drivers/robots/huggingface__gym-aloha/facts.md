# Facts and tags for gh.huggingface/gym-aloha

Every fact cites its source at commit `bd3325740ea8d1c97411c41ea1e0f4ce0a7de8da`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The action space is a Box with low -1 and high 1 shaped by the ACTIONS list | upstream_code | gym_aloha/env.py:86 |
| ACTIONS lists six absolute arm joints and then the normalized gripper position (0 close, 1 open), for the left arm and then for the right arm | upstream_code | gym_aloha/constants.py:29-47 |
| The control timestep DT is 0.02 and FPS is 50; the comment on the DT line derives 50 hz from it | upstream_code | gym_aloha/constants.py:4-5 |
| The simulation's control timestep is that DT, passed to the dm_control Environment as control_timestep | upstream_code | gym_aloha/env.py:133-135 |
| The observation of obs_type pixels_agent_pos is a Dict of a nested pixels Dict whose top member is a uint8 Box of 0 to 255 shaped observation_height x observation_width x 3, and an agent_pos Box between -1000.0 and 1000.0 | upstream_code | gym_aloha/env.py:64-84 |
| observation_width defaults to 640 and observation_height to 480 | upstream_code | gym_aloha/env.py:30-31 |
| The observation image is rendered 480 high and 640 wide from the top camera | upstream_code | gym_aloha/tasks/sim.py:92 |
| The gripper observation is the finger position normalized by normalize_puppet_gripper_position, so 0 is closed and 1 is open | upstream_code | gym_aloha/constants.py:94-97 |
| The start qpos is waist 0, shoulder -0.96, elbow 1.16, forearm roll 0, wrist angle -0.3, wrist rotate 0 and fingers 0.02239 and -0.02239 for each arm | upstream_code | gym_aloha/constants.py:50-67 |
| reset(seed) seeds the task's random generator and replaces its numpy RandomState with RandomState(seed) | upstream_code | gym_aloha/env.py:153-156 |
| The object poses are drawn uniformly: the peg x from 0.1 to 0.2, the socket x from -0.2 to -0.1, both y from 0.4 to 0.6 and both z from 0.05 to 0.05 | upstream_code | gym_aloha/utils.py:20-38 |
| step returns terminated = is_success = (reward == 4), truncated False and an info carrying is_success | upstream_code | gym_aloha/env.py:180-187 |
| The InsertionTask reward is 1 when both grippers touch peg and socket, 2 when neither object touches the table, 3 when the peg touches a socket and 4 when the red peg touches the pin | upstream_code | gym_aloha/tasks/sim.py:208-219 |
| The TransferCubeTask reward rises from 1 to 4 with the right gripper, the lift, the left gripper and a transfer that leaves the table | upstream_code | gym_aloha/tasks/sim.py:140-149 |
| AlohaInsertion-v0 registers AlohaEnv with max_episode_steps 300, obs_type pixels and task insertion, and AlohaTransferCube-v0 registers the same class with task transfer_cube | upstream_code | gym_aloha/__init__.py:3-21 |
| Both registered environments set nondeterministic True because even after seeding the rendered observations are slightly different | upstream_code | gym_aloha/__init__.py:7-9 |
| The state observation type is not implemented: obs_type state raises NotImplementedError | upstream_code | gym_aloha/env.py:46-47 |
| close does nothing | upstream_code | gym_aloha/env.py:189-190 |

Limits: the driver declares none of its own. The only bound of an input is the action space, which the bridge derives
from the environment (`Box(low=-1, high=1)` with 14 elements, so `action.values` is bounded element by element between
-1 and 1, with the source `upstream_code` and the ref `gym_aloha/env.py:86`), and `ticks` (1 to `max_ticks`, 10000 by
default). The device is simulated (R0), so no limit is `operator_required`.

Configuration: `env_id = "gym_aloha/AlohaInsertion-v0"` with `env_kwargs = {"task": "insertion", "obs_type":
"pixels_agent_pos"}`. The registered kwargs are `obs_type="pixels"` and `task="insertion"` (`gym_aloha/__init__.py:10`);
`pixels_agent_pos` is the other observation the README documents (`README.md:95`) and it carries the 14 joint positions
next to the image.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:gym_aloha/AlohaInsertion-v0`, level F1
(rigid-body physics of two arms in a MuJoCo scene, no contacts, no actuator, sensor or noise model), determinism
`seeded` with `seed_control` `parameter`, timestep 20 ms (DT 0.02 s, `gym_aloha/constants.py:4`), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled, that the upstream registers
the environment `nondeterministic`, and that this package's fake was not compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step,
reset or seed is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the
state stays readable.

Tags: aloha, bimanual, manipulation, reinforcement-learning, simulation, mujoco, gymnasium
