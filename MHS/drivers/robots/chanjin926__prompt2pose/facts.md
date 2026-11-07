# Facts and tags for gh.chanjin926/prompt2pose

Every fact cites its source at commit `615098ccc37f2af4e7e1a1ed2d705c5fef279c23`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| ArrayCan-v1 is registered with max_episode_steps=50 | upstream_code | envs/array_can.py:21 |
| The default robot is panda_wristcam, the initial joint-position noise is 0.02, and the task holds 5 cans | upstream_code | envs/array_can.py:27-30 |
| The supported robots are panda_wristcam, panda and fetch | upstream_code | envs/array_can.py:23 |
| The can model is scaled by 0.03 with radius 1 m and height 3.5 m | upstream_code | envs/array_can.py:52-54 |
| Each can has mass 0.5 | upstream_code | envs/array_can.py:59 |
| The can xy positions start from torch.rand((b, 2)) * 0.26 - 0.13 and are sampled in the region [-0.15, -0.15] to [0.15, 0.15] | upstream_code | envs/array_can.py:85-86 |
| Equal spacing passes when at least one of the two smallest pairwise distance gaps is at most 0.01 | upstream_code | envs/array_can.py:111-114 |
| The linear arrangement is tested only for 3 cans, with an area tolerance of 0.001 | upstream_code | envs/array_can.py:116-124 |
| Success requires equal spacing, a linear arrangement and no grasped can | upstream_code | envs/array_can.py:128-131 |
| The dense reaching reward is 2 * (1 - tanh(5 * min_dist)) from the TCP to the nearest can | upstream_code | envs/array_can.py:153-161 |
| When obs_mode contains state the observation adds the TCP pose, each can pose, the TCP-to-can and the can-to-can position vectors | upstream_code | envs/array_can.py:140-150 |
| The base camera is 512x512 with a pi/2 field of view, near plane 0.01 and far plane 100 | upstream_code | envs/array_can.py:36 |
| The robot base is placed at [-0.615, 0, 0] | upstream_code | envs/array_can.py:44 |

Limits: the driver declares none. The `cap.world.step.v1` class bounds `ticks` to 1 to 10000, and the bridge
would derive the action from the environment's action space; the upstream space comes from ManiSkill's `BaseEnv`
and the Panda agent, which are external to the clone and not stated in it, so the fake exposes no action space and
the step action is an open object with no bounds. No limit is `operator_required`, because the device is simulated
(R0) and nothing in this repository states a physical bound.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `ManiSkill:SAPIEN/ArrayCan-v1`, level F0 (the deployed
fake is a kinematic task model, not the SAPIEN physics), determinism `seeded` with `seed_control` `parameter`,
`timestep_ms` 0 because the clone does not state ManiSkill's control period, `realtime_factor` 0, clock `lockstep`,
reset `full`, no snapshot and restore. The gaps say that the robot, contacts, action/observation arrays, camera
images and upstream dynamics are not modelled and that the fake was never compared with the upstream environment.

Safety: simulated R0 device with only `cap.world.*` classes (all R0). The e-stop is the runtime's software latch (no
native stop exists); after it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state
stays readable. The simulated Panda arm inside the upstream environment is part of the model; this package cannot
command hardware.

Tags: arraycan, maniskill, sapien, tabletop, reinforcement-learning, simulation, gymnasium
