# Facts and tags for gh.isaac-sim/omniisaacgymenvs

Every fact cites its source at commit `f8f91bcf73cfd8ede2eab70e19dd70162abf9775`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository contains reinforcement-learning examples that run with Isaac Sim and are built on omni.isaac.core and omni.isaac.gym | vendor_doc | README.md:9 |
| The examples rely on the latest Isaac Sim release and pin it to 4.0.0, installed separately | vendor_doc | README.md:31-33 |
| VecEnvRLGames extends VecEnvBase, imported from omni.isaac.gym.vec_env, so its simulator and base interface come from outside the clone | upstream_code | omniisaacgymenvs/envs/vec_env_rlgames.py:34-38 |
| VecEnvRLGames.step takes an actions tensor and returns four values: an observation dict, rewards, resets and extras | upstream_code | omniisaacgymenvs/envs/vec_env_rlgames.py:52-104 |
| VecEnvRLGames.reset takes seed and options, resets the task, applies one zero action and returns the observation dict; its body does not read seed or options | upstream_code | omniisaacgymenvs/envs/vec_env_rlgames.py:106-115 |
| The observation dict carries the observations under obs and the task states under states | upstream_code | omniisaacgymenvs/envs/vec_env_rlgames.py:102 |
| The observations are clamped to +-clipObservations in the wrapper | upstream_code | omniisaacgymenvs/envs/vec_env_rlgames.py:39-40 |
| The actions are clamped to +-clipActions before the task sees them | upstream_code | omniisaacgymenvs/envs/vec_env_rlgames.py:77 |
| Cartpole sets clipActions to 1.0, clipObservations to 5.0, resetDist to 3.0 and maxEffort to 400.0 | upstream_code | omniisaacgymenvs/cfg/task/Cartpole.yaml:10-14 |
| RLTask initializes a task's action space to a Box of -1 to 1 per action dimension and its observation space to a Box of -inf to inf per observation dimension unless the task sets its own | upstream_code | omniisaacgymenvs/tasks/base/rl_task.py:127-136 |
| CartpoleTask declares four observations and one action | upstream_code | omniisaacgymenvs/tasks/cartpole.py:46-47 |
| The Cartpole observation is [cart position, cart velocity, pole position, pole velocity] | upstream_code | omniisaacgymenvs/tasks/cartpole.py:91-103 |
| The Cartpole action is a force on the cart: maxEffort times the first action component | upstream_code | omniisaacgymenvs/tasks/cartpole.py:118-119 |
| A Cartpole reset samples the cart position in [-1, 1], the pole position in [-0.125 pi, 0.125 pi], the cart velocity in [-0.5, 0.5] and the pole velocity in [-0.25 pi, 0.25 pi] | upstream_code | omniisaacgymenvs/tasks/cartpole.py:127-135 |
| The Cartpole reward is 1 - pole_pos^2 - 0.01*abs(cart_vel) - 0.005*abs(pole_vel), replaced by -2 when abs(cart_pos) > resetDist or abs(pole_pos) > pi/2 | upstream_code | omniisaacgymenvs/tasks/cartpole.py:153-156 |
| Cartpole flags a reset when abs(cart_pos) > resetDist, abs(pole_pos) > pi/2, or the progress reaches the episode length | upstream_code | omniisaacgymenvs/tasks/cartpole.py:160-163 |
| The Cartpole episode length is 500 steps | upstream_code | omniisaacgymenvs/tasks/cartpole.py:44 |
| Cartpole sets controlFrequencyInv to 2 (about 60 Hz) and the physics dt to 0.0083 s (1/120 s) | upstream_code | omniisaacgymenvs/cfg/task/Cartpole.yaml:15-18 |
| Cartpole defaults to 512 environments | upstream_code | omniisaacgymenvs/cfg/task/Cartpole.yaml:8 |
| The Hydra task map maps the name Cartpole to CartpoleTask | upstream_code | omniisaacgymenvs/utils/task_util.py:55-61 |
| initialize_task instantiates task_map[cfg['task_name']] | upstream_code | omniisaacgymenvs/utils/task_util.py:97-99 |
| The training script constructs VecEnvRLGames with headless, sim_device, livestream, viewport and experience arguments | upstream_code | omniisaacgymenvs/scripts/rlgames_train.py:105-111 |
| The install_requires list is numpy, protobuf, omegaconf, hydra-core, urllib3, rl-games, moviepy and gymnasium 0.28.1 | upstream_code | setup.py:41-50 |

Limits: the driver declares none. The only bound is the environment's action space, which the Gymnasium bridge derives
from the backend (`Box` of one value in [-1, 1]; `action.values` in the reference, with the bridge's source
`upstream_code` and ref `omniisaacgymenvs/tasks/base/rl_task.py:129-131`), plus `ticks` (1 to `max_ticks`, 10000 by
default). The task is simulated (R0), so no limit is `operator_required` and there is no site-limits overlay.

The action space is the `RLTask` default (`rl_task.py:127-131`) for the one Cartpole action (`cartpole.py:47`). The
bridge derives it from the backend object; it is not a driver-authored `Limit`, and the reviewer should read it
together with `Cartpole.yaml:14` (`clipActions` 1.0), which the upstream applies again before the task sees the action
(`vec_env_rlgames.py:77`).

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:omniisaacgymenvs Cartpole stand-in (Isaac Sim 4.0
target)`, level F0 (no dynamics claim; the fake's action-driven velocities are placeholders), determinism `seeded` with
`seed_control` `parameter`, timestep 16.6 ms (two 0.0083 s physics steps, `Cartpole.yaml:15-18`), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The gaps name what is missing: no rigid-body dynamics or
contacts, Isaac Sim/PhysX never opened, one environment instead of the upstream's 512 (`Cartpole.yaml:8`) and scalar
instead of per-environment rewards, a reset that differs from `VecEnvRLGames.reset`, no rendering/cameras/domain
randomisation/task states, and no comparison with an Isaac Sim run.

Safety: simulated R0 environment. The upstream has no native stop; the e-stop is the runtime's software latch, after
which no step, reset or seed is accepted until `mhs.safety.reset` clears it, and the last state stays readable.

Tags: isaac-sim, omniisaacgymenvs, cartpole, reinforcement-learning, simulation, vectorized
