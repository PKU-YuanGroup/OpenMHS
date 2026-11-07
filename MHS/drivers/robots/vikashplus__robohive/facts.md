# Facts and tags for gh.vikashplus/robohive

Every fact cites its source at commit `6c14798e48b9904dd8c9151837a1d2468b87bcf3`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or `upstream_code`
(`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| FrankaReachFixed-v0 is registered with entry point robohive.envs.arms.reach_base_v0:ReachBaseV0 and max_episode_steps=50 | upstream_code | robohive/envs/arms/__init__.py:21-24 |
| ReachBaseV0 declares the observation keys qp_robot, qv_robot and reach_err | upstream_code | robohive/envs/arms/reach_base_v0.py:17-19 |
| The observation is the full qpos and qvel as qp_robot and qv_robot plus reach_err, the target site position minus the robot site position | upstream_code | robohive/envs/arms/reach_base_v0.py:74-81 |
| The dense reward weights are reach -1.0, bonus 4.0 and penalty -50 | upstream_code | robohive/envs/arms/reach_base_v0.py:22-26 |
| The reach task uses far_th 1.0 and counts a bonus below 0.1 and 0.05: solved is reach_dist < 0.050 and done is reach_dist > 1.0 | upstream_code | robohive/envs/arms/reach_base_v0.py:85-96 |
| The environment normalizes actions by default (normalize_act=True) and builds the action space as gym.spaces.Box(-1, 1) of sim.model.nu elements | upstream_code | robohive/envs/env_base.py:97-99 |
| The observation space is a gym.spaces.Box of -10 to 10 for every element of the observation vector | upstream_code | robohive/envs/env_base.py:139 |
| MujocoEnv.step clips the action to the action space before it is sent to the robot | upstream_code | robohive/envs/env_base.py:254-260 |
| Under gymnasium, reset returns (observation, {}) | upstream_code | robohive/envs/env_base.py:512-513 |
| Under gymnasium, the step result is the five-tuple (obs, reward, terminal, False, info) | upstream_code | robohive/envs/env_base.py:279-282 |
| The registration comment gives 50 steps of 40 skips at 2 ms, i.e. a 0.08 s environment step and a 4 s episode | upstream_code | robohive/envs/arms/__init__.py:24 |
| ReachBaseV0 defaults frame_skip to 40 | upstream_code | robohive/envs/arms/reach_base_v0.py:53 |
| dt is the model timestep multiplied by frame_skip | upstream_code | robohive/envs/env_base.py:521-522 |
| The observation vector is built by concatenating the declared observation keys, so its width is the sum of the key lengths | upstream_code | robohive/envs/env_base.py:334 |
| A reset samples the target site position uniformly from target_xyz_range with the environment random generator | upstream_code | robohive/envs/arms/reach_base_v0.py:100-103 |

Limits: the driver declares none. The action bound is the environment action space, which the Gymnasium bridge derives
from the live environment (`Box(-1, 1)` over `sim.model.nu` elements, `robohive/envs/env_base.py:97-99`, with no
source and the reference `action_space of the fake backend .fake:FakeReachBaseV0`); `ticks` is bounded by the bridge
(1 to `max_ticks`, 10000 by default). The device is simulated (R0), so no limit is `operator_required` and no operator
overlay is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `robohive:FrankaReachFixed-v0 (MuJoCo)`, level F1
(rigid-body dynamics with contacts in the upstream model), determinism `seeded` with `seed_control` `parameter`,
timestep 80 ms (the registration comment's 2 ms at `robohive/envs/arms/__init__.py:24` times `frame_skip` 40 at
`reach_base_v0.py:53`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say
that the fake is a kinematic stand-in, that upstream MuJoCo was never run here and that no physical device was
attached. The fake's array dimensions are test data, not device facts: the scene model lives in a git submodule of
the clone, so G4 cannot cite it from the pinned commit.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: robohive, franka, reach, manipulation, reinforcement-learning, mujoco, simulation, gymnasium
