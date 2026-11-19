# Facts and tags for gh.zihanwang0422/legged_rl_lab

Every fact cites its source at commit `386ee24bc62c8033641d65b940dc2cf1dec56545`: `vendor_doc` (a text file of the
clone, such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository targets Isaac Sim 5.1.0 and Isaac Lab 2.3.0 and its documented environment uses Python 3.11 | vendor_doc | README.md:3-5 |
| The cross-embodied G1+Go2 flat task is registered as LeggedRLLab-Isaac-CrossEmboided-Flat-G1Go2-Mixed-v0 with CrossEmbodiedG1Go2Env as its entry point | upstream_code | source/legged_rl_lab/legged_rl_lab/tasks/locomotion/cross_emboided/config/g1go2_mixed/__init__.py:20-33 |
| The scene spawns a 29-DOF Unitree G1 and a 12-DOF Unitree Go2 in every environment; the first n // 2 environments make G1 active and the second half make Go2 active | upstream_code | source/legged_rl_lab/legged_rl_lab/tasks/locomotion/cross_emboided/config/g1go2_mixed/g1go2_flat_env_cfg.py:4-10 |
| The shipped configuration sets num_envs to 512 with an environment spacing of 4.0 m | upstream_code | source/legged_rl_lab/legged_rl_lab/tasks/locomotion/cross_emboided/config/g1go2_mixed/g1go2_flat_env_cfg.py:519-522 |
| The inactive-robot parking constant _PARK_ALTITUDE is 100.0 | upstream_code | source/legged_rl_lab/legged_rl_lab/tasks/locomotion/cross_emboided/config/g1go2_mixed/g1go2_flat_env_cfg.py:549-550 |
| The policy action is one unified 29-dimensional vector; G1 uses all 29 dims and Go2 applies only the first 12 and discards dims 12-28 | upstream_code | source/legged_rl_lab/legged_rl_lab/tasks/locomotion/cross_emboided/mdp/cross_embodied_mdp.py:645-653 |
| The raw action is scaled by 0.5 for G1 and 0.25 for Go2 | upstream_code | source/legged_rl_lab/legged_rl_lab/tasks/locomotion/cross_emboided/config/g1go2_mixed/g1go2_flat_env_cfg.py:197-198 |
| The action term computes scaled = action * scale and joint targets = default joint position + scaled, and stores the Go2-masked scaled action in _last_scaled | upstream_code | source/legged_rl_lab/legged_rl_lab/tasks/locomotion/cross_emboided/mdp/cross_embodied_mdp.py:689-710 |
| last_action_cross clones action_manager.action and zeroes unused Go2 dimensions | upstream_code | source/legged_rl_lab/legged_rl_lab/tasks/locomotion/cross_emboided/mdp/cross_embodied_mdp.py:117-127 |
| The policy joint velocity observation has scale 0.05 and last_action uses last_action_cross | upstream_code | source/legged_rl_lab/legged_rl_lab/tasks/locomotion/cross_emboided/config/g1go2_mixed/g1go2_flat_env_cfg.py:150-155 |
| The critic joint velocity observation has scale 0.05 and last_action uses last_action_cross | upstream_code | source/legged_rl_lab/legged_rl_lab/tasks/locomotion/cross_emboided/config/g1go2_mixed/g1go2_flat_env_cfg.py:176-178 |
| The actor observation is 98 dimensions [robot_id(2), base angular velocity(3), projected gravity(3), command(3), joint position(29), joint velocity(29), last action(29)] and the critic observation is 101 dimensions, adding base linear velocity(3) | upstream_code | source/legged_rl_lab/legged_rl_lab/tasks/locomotion/cross_emboided/config/g1go2_mixed/g1go2_flat_env_cfg.py:15-30 |
| The velocity command samples x and y linear velocity and yaw rate uniformly from -1.0 to 1.0 and resamples them every 10 s | upstream_code | source/legged_rl_lab/legged_rl_lab/tasks/locomotion/cross_emboided/config/g1go2_mixed/g1go2_flat_env_cfg.py:216-227 |
| Termination selects base_below_threshold_cross with min_height 0.25 and mdp.time_out with time_out=True | upstream_code | source/legged_rl_lab/legged_rl_lab/tasks/locomotion/cross_emboided/config/g1go2_mixed/g1go2_flat_env_cfg.py:493-497 |
| The control period is four 5 ms simulation steps (20 ms) and the configured episode length is 20 s | upstream_code | source/legged_rl_lab/legged_rl_lab/tasks/locomotion/cross_emboided/config/g1go2_mixed/g1go2_flat_env_cfg.py:533-535 |
| The G1 initial-state configuration sets pos=(0.0, 0.0, 0.8) | upstream_code | source/legged_rl_lab/legged_rl_lab/assets/unitree.py:332-333 |
| The shared alive reward term has weight 0.15 | upstream_code | source/legged_rl_lab/legged_rl_lab/tasks/locomotion/cross_emboided/config/g1go2_mixed/g1go2_flat_env_cfg.py:366 |
| is_alive_cross returns the inverse of termination_manager.terminated as floats | upstream_code | source/legged_rl_lab/legged_rl_lab/tasks/locomotion/cross_emboided/mdp/cross_embodied_mdp.py:187-193 |
| The package setup metadata declares license Apache 2.0 | upstream_code | source/legged_rl_lab/setup.py:30 |

Limits: the driver declares none. The only command bound is the environment's action space, which the bridge derives
from the environment: the fake publishes an unbounded 29-element Box because the clone's action term defines no clipping
(`cross_embodied_mdp.py:689-710`); the external Isaac Lab action manager's own space was not inspected. The `ticks`
input is bounded 1 to 10000 by the bridge. The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:legged_rl_lab-g1go2-kinematic-fake`, level F0
(kinematic positions, no dynamics), determinism `seeded` with `seed_control` `parameter`, timestep 20 ms (decimation 4 x
5 ms, `g1go2_flat_env_cfg.py:533-535`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore.
The gaps name the missing dynamics, the one-G1-environment scope, the placeholder base height, the omitted reward terms,
the analytic observation values and the untested Isaac Sim/GPU dependency. Joint velocity observations apply the
configured scale 0.05, while last_action follows `action_manager.action` rather than the action term's `_last_scaled`
buffer. The fake's alive score is a synthetic use of weight 0.15, zero when terminated; it does not reproduce the
external reward manager's integration. Its 1000-step timeout and explicit post-terminal reset are stand-in lifecycle
choices; inherited automatic resets were not reproduced.

Safety: a simulated R0 fake-only device. The e-stop is the runtime's software latch; after it no step, world reset or
seed is accepted until `mhs.safety.reset` clears the latch, and the cached state stays readable. Latch release alone
does not change the stand-in state. This establishes no native Isaac Sim stop.

Only `backends['fake']` is declared. The family's implicit `gymnasium.make` fallback does not supply the required
`cfg` (g1go2_flat_env_cfg.py:573-578), task registration, batched tensor conversion or app lifecycle. The upstream
script launches AppLauncher before its environment imports (scripts/rsl_rl/train.py:59-61) and creates the task with
`cfg=env_cfg` (:212). A future live adapter needs lifecycle isolation, vector result conversion and a native stop
with read-back. The fake's single G1 slice is not obtained by setting num_envs=1 upstream: the class splits at
`num_envs // 2` and that would select only Go2 (:578-587).

The source also contains Go1/G1 hardware deployment scripts and Unitree SDK submodules (deploy/go1_deploy/sim2real_walk.py
and `.gitmodules`); none is served. The parking helper sets inactive robots' world z to 100, rather than adding 100
to the environment origin z (g1go2_flat_env_cfg.py:607-615); parking is outside the fake's scope.

The card retains `NOASSERTION` and `publish_review: required`. Setup metadata declares Apache 2.0
(source/legged_rl_lab/setup.py:30), and the selected environment has an Apache-2.0 header (:1-2); these file notices
do not resolve publication permission for the whole repository. That decision remains with the owner.

Tags: legged-robot, locomotion, cross-embodied, reinforcement-learning, isaac-lab, simulation, gymnasium
